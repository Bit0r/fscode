#!/usr/bin/env python3

import os
import sys
import shlex
from pathlib import Path
import tempfile
from textwrap import dedent

import fire
from plumbum import CommandNotFound, local
from rich.console import Console

from .plan import graph2operations


class FSCode:
    """
    A CLI tool for batch processing file paths using an external editor.

    This tool receives a list of file paths, opens them in a temporary TSV file
    for editing, and then generates a script to apply the changes (copy, move, remove).
    """

    def __init__(self):
        self._console = Console()

    def _get_editor(self, editor_cmd: str):
        """
        Validates the given editor command string and returns a runnable plumbum command.
        Exits with a helpful message if the command is not found.
        """
        # The parameter no longer needs a default value, as it will always receive a string from the run method.
        try:
            cmd_parts = shlex.split(editor_cmd)
            # Try to create a plumbum object from the parsed command.
            return local[cmd_parts[0]][cmd_parts[1:]]
        except CommandNotFound:
            # If the command does not exist (e.g., 'code' is not installed), catch the exception and provide a friendly hint.
            prompt_text = f"""
            [bold red]Error: Editor command not found: '{editor_cmd}'[/]
            Please check your command, $VISUAL/$EDITOR, or install a default editor like VS Code.
            Some common choices: 'code -w', 'msedit', 'micro'"""
            prompt_text = dedent(prompt_text[1:])
            self._console.print(prompt_text)
        sys.exit(1)

    def _generate_temp_file_content(self, file_paths: list[str]):
        """
        Generates the content for the temporary TSV file.
        Returns a mapping of ID to original path and the file content string.
        """
        id2path = {}
        tips = r"""
            # File Operation Plan
            # Format: <ID>	<Path>
            # Lines starting with '#' are ignored.
            # To delete a file, remove its line or comment it out.
            # To rename/move a file, edit its path.
            # To copy a file, add a new line with the same ID and a different path.
            # --- IMPORTANT RULES FOR SPECIAL CHARACTERS ---
            # If your filename contains characters that need to be escaped in the shell,
            # please escape them according to the bash's rules (e.g., add quotes)."""
        tips = dedent(tips[1:])
        lines = [tips]
        for idx, path in enumerate(file_paths, 1):
            id2path[idx] = path
            # Handle special characters in the path.
            quoted_path = shlex.quote(path)
            lines.append(f'{idx}\t{quoted_path}')
        return id2path, '\n'.join(lines) + '\n'

    def _parse_edited_file(self, temp_file_path: Path, id2path: dict[int, str]):
        """
        Parses the edited temporary file to extract the desired file operations.
        """
        edges = []

        with temp_file_path.open('r') as f:
            # Use enumerate to get line numbers for better error messages
            for idx, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    self._console.print(
                        f'[bold red]Error:[/] Malformed line {idx}: {line}'
                    )
                    sys.exit(1)

                file_id_str, quoted_path = parts

                file_id = int(file_id_str)
                # Restore special characters from the path.
                new_path = shlex.split(quoted_path)[0]

                original_path = id2path[file_id]
                edges.append((original_path, new_path))

        return edges

    def run(
        self,
        *paths: str,
        editor: str = os.getenv('VISUAL', os.getenv('EDITOR', 'code -w')),
        output_script: str | Path = 'file_ops.sh',
        edit_suffix: str = '.sh',
        rm: str = 'rm',
        cp: str = 'cp',
        mv: str = 'mv',
        mv_temp_filename: str = './__mv_tmp',
        exchange: bool = False,
        mv_exchange: str = 'mv --exchange',
        cmd_prefix: str | None = None,
    ):
        """
        Main execution flow.

        :param paths: File paths to process. Can be provided as arguments or via stdin.
        :param editor: The editor command to use (e.g., "msedit", "code -w").
                        Defaults to $VISUAL, $EDITOR, or 'code -w'.
        :param output_script: Path to write the generated shell script.
        :param edit_suffix: Suffix for the temporary editing file. Defaults to '.sh'.
        :param is_exchange: Use an exchange-based move for cycles, avoiding temporary files.
        :param cp: The command to use for copy operations.
        :param rm: The command to use for remove operations.
        :param mv: The command to use for move operations.
        :param mv_temp_file: Path for the temporary file used during move operations.
        :param mv_exchange: The command for atomic swap/exchange moves.
        :param cmd_prefix: An optional command prefix to prepend to all commands.
        """
        output_script_path = Path(output_script)
        input_paths = list(paths)
        if not sys.stdin.isatty():
            input_paths.extend(line.strip() for line in sys.stdin if line.strip())

        if not input_paths:
            self._console.print(
                '[bold yellow]No input file paths provided. Exiting.[/]'
            )
            return

        if cmd_prefix:
            # Prepend the command prefix to all commands
            mv = f'{cmd_prefix} {mv}'
            cp = f'{cmd_prefix} {cp}'
            rm = f'{cmd_prefix} {rm}'
            mv_exchange = f'{cmd_prefix} {mv_exchange}'

        id2path, temp_content = self._generate_temp_file_content(input_paths)

        try:
            # Create a temporary file that we control
            tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=edit_suffix, text=True)
            tmp_path = Path(tmp_path_str)

            tmp_path.write_text(temp_content)

            # 2. Open in editor
            editor_cmd = self._get_editor(editor)
            prompt_text = f"""
            Opening temporary file in editor: [cyan]{tmp_path}[/]
            Save and close the editor to continue...
            """
            prompt_text = dedent(prompt_text[1:])
            self._console.print(prompt_text)

            # This call blocks until the editor is closed
            editor_cmd(tmp_path)

            self._console.print('[green]Editor closed. Processing changes...[/]')

            # 3. Parse the results
            original_nodes = list(id2path.values())
            edges = self._parse_edited_file(tmp_path, id2path)

            print(original_nodes)
            print(edges)

            # 4. Call the planning algorithm
            operations = graph2operations(
                nodes=original_nodes,
                edges=edges,
                tmp_name=mv_temp_filename,
                mv=shlex.split(mv),
                cp=shlex.split(cp),
                rm=shlex.split(rm),
                is_exchange=exchange,
                mv_exchange=shlex.split(mv_exchange),
            )

            # 5. Generate and write script
            header = """
            #!/bin/sh
            # Run this script in the same directory where you ran the original command.
            # Example: source ./file_ops.sh
            """
            header = dedent(header[1:])
            script_content = [header]
            for op in operations:
                # Use shlex to join the command parts correctly.
                cmdline = shlex.join(op)
                # Add the command line to the script content.
                script_content.append(cmdline)

            output_script_path.write_text('\n'.join(script_content) + '\n')

            self._console.print(
                f'Generated script at [bold green]{output_script_path}[/]'
            )

        finally:
            # 6. Clean up the temporary file
            if 'tmp_fd' in locals() and tmp_fd:
                os.close(tmp_fd)
            if 'tmp_path' in locals() and tmp_path and tmp_path.exists():
                tmp_path.unlink()
                self._console.print(f'Cleaned up temporary file: [cyan]{tmp_path}[/]')


def main():
    """Main entry point for the fscode CLI."""
    fscode = FSCode()
    fire.Fire(fscode.run)


if __name__ == '__main__':
    main()
