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
            if not cmd_parts:
                self._console.print('[bold red]Error: Editor command is empty.[/]')
                sys.exit(1)

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
        tips = r"""
            # File Operation Plan
            # Format: <ID> <Path>
            # Lines starting with '#' are ignored.
            # To delete a file, remove its line or comment it out.
            # To create a new file, add a new line with ID 0.
            # To rename/move a file, edit its path.
            # To copy a file, add a new line with the same ID and a different path.
            # --- IMPORTANT RULES FOR SPECIAL CHARACTERS ---
            # If your filename contains characters that need to be escaped in the shell,
            # please escape them according to the bash's rules (e.g., add quotes).
            """
        tips = dedent(tips[1:])
        lines = [tips]

        nodes = [''] * (len(file_paths) + 1)
        # 0 is the empty path
        for idx, path in enumerate(file_paths, 1):
            nodes[idx] = path
            # Handle special characters in the path.
            lines.append(shlex.join([str(idx), path]))

        return nodes, '\n'.join(lines) + '\n'

    def _parse_edited_file(self, temp_file_path: Path, origin_nodes: list[str]):
        """
        Parses the edited temporary file to extract the desired file operations.
        """
        edges = []

        with temp_file_path.open() as f:
            # Use enumerate to get line numbers for better error messages
            for idx, line in enumerate(f, 1):
                parts = shlex.split(line, comments=True)
                if not parts:
                    continue
                elif len(parts) != 2:
                    self._console.print(
                        f'[bold red]Error:[/] Malformed line {idx}: {line}'
                    )
                    sys.exit(1)

                file_id, new_path = parts
                file_id = int(file_id)

                if file_id >= len(origin_nodes):
                    self._console.print(
                        f'[bold red]Error:[/] Invalid ID {file_id} on line {idx}: {line}'
                    )
                    sys.exit(1)

                original_path = origin_nodes[file_id]
                edges.append((original_path, new_path))

        return edges

    def run(
        self,
        *paths: str,
        editor: str = os.getenv('VISUAL', os.getenv('EDITOR', 'code -w')),
        output_script: str | Path = 'file_ops.sh',
        edit_suffix='.sh',
        null=False,
        remove='rm',
        copy='cp',
        move='mv',
        create='touch',
        exchange='mv --exchange',
        move_tmp_filename='./__mv_tmp',
        is_exchange=False,
        cmd_prefix: str | None = None,
    ):
        """
        Main execution flow.

        :param paths: File paths to process. Can be provided as arguments or via stdin.
        :param editor: The editor command to use (e.g., "msedit", "code -w").
                        Defaults to $VISUAL, $EDITOR, or 'code -w'.
        :param output_script: Path to write the generated shell script.
        :param edit_suffix: Suffix for the temporary editing file. Defaults to '.sh'.
        :param null: Whether to use null-separated input.
        :param copy: The command to use for copy operations.
        :param remove: The command to use for remove operations.
        :param move: The command to use for move operations.
        :param exchange: The command for atomic swap/exchange moves.
        :param move_tmp_filename: Path for the temporary file used during move operations.
        :param is_exchange: Use an exchange-based move for cycles, avoiding temporary files.
        :param cmd_prefix: An optional command prefix to prepend to all commands.
        """
        output_script_path = Path(output_script)
        input_paths = list(paths)
        if not sys.stdin.isatty():
            if null:
                # Using the '\0' delimiter prevents stream reading; the entire input must be read at once.
                stdin_content = sys.stdin.buffer.read().decode(errors='surrogateescape')
                stdin_paths = [p for p in stdin_content.strip('\0').split('\0') if p]
            else:
                # We can't use shlex.split here, only line.rstrip, because shlex.split would separate paths with spaces.
                # We use rstrip instead of strip because we only want to remove trailing \r or \n.
                stdin_paths = [
                    line.rstrip('\r\n') for line in sys.stdin if line.rstrip('\r\n')
                ]

            input_paths.extend(stdin_paths)

        if not input_paths:
            self._console.print(
                '[bold yellow]No input file paths provided. Exiting.[/]'
            )
            return

        # Split commands into lists
        cmds = [remove, create, copy, move, exchange]
        if cmd_prefix:
            cmd_prefix = shlex.split(cmd_prefix, comments=True)
        for i, cmd in enumerate(cmds):
            cmd = shlex.split(cmd, comments=True)
            if cmd_prefix:
                cmd = [*cmd_prefix, *cmd]
            # Update the command in the list
            cmds[i] = cmd
        # Unpack the commands
        remove, create, copy, move, exchange = cmds

        origin_nodes, temp_content = self._generate_temp_file_content(input_paths)

        try:
            # Create a temporary file that we control
            _, tmp_path_str = tempfile.mkstemp(suffix=edit_suffix, text=True)
            tmp_path = Path(tmp_path_str)

            # Write to the file and then close it to ensure the content is flushed to disk.
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
            edges = self._parse_edited_file(tmp_path, origin_nodes)

            # 4. Call the planning algorithm
            operations = graph2operations(
                nodes=origin_nodes,
                edges=edges,
                tmp_name=move_tmp_filename,
                remove=remove,
                create=create,
                move=move,
                copy=copy,
                exchange=exchange,
                is_exchange=is_exchange,
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
                if op[0] == '#':
                    # is a comment
                    # Join the comment parts correctly.
                    comment = ' '.join(op)
                    # Add the comment to the script content.
                    script_content.append(comment)
                else:
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
            if 'tmp_path' in locals() and tmp_path and tmp_path.exists():
                tmp_path.unlink()
                self._console.print(f'Cleaned up temporary file: [cyan]{tmp_path}[/]')


def main():
    """Main entry point for the fscode CLI."""
    fscode = FSCode()
    fire.Fire(fscode.run)


if __name__ == '__main__':
    main()
