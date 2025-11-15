#!/usr/bin/env python3

import os
import sys
import shlex
from pathlib import Path
import tempfile
from textwrap import dedent

import fire
from plumbum import FG, CommandNotFound, local
from fastnanoid import generate
from rich.console import Console

from .plan import GraphOperationGenerator

platform_cmds = {
    # editor
    'code -w': {'nt': 'code.cmd -w'},
    # remove
    'rm -IR': {'win32': 'del -Confirm -Recurse'},
    # move
    'mv -iT': {
        'darwin': 'mv -i',
        'win32': 'move -Confirm',
    },
    'mv --exchange -iT': {},
    # copy
    'cp -iRT': {
        'darwin': 'cp -iR',
        'win32': 'copy -Confirm -Recurse',
    },
    'ln -inT': {
        'darwin': 'ln -in',
        'win32': 'ni -Confirm -Type HardLink -Value',
    },
    # create
    'touch': {'win32': 'ni'},
    'mkdir -p': {'win32': 'ni -Confirm -Type Directory'},
    'ln -sinT': {
        'darwin': 'ln -sinF',
        'win32': 'ni -Confirm -Type SymbolicLink -Value',
    },
}


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
            return local[cmd_parts[0]][*cmd_parts[1:]]
        except CommandNotFound:
            # If the command does not exist (e.g., 'code' is not installed), catch the exception and provide a friendly hint.
            prompt_text = f"""
            [bold red]Error: Editor command not found: '{editor_cmd}'[/]
            Please check your command, $VISUAL/$EDITOR, or install a default editor like VS Code.
            Some common choices: 'code -w', 'msedit', 'micro'"""
            prompt_text = dedent(prompt_text[1:])
            self._console.print(prompt_text)
            sys.exit(1)

    def _generate_temp_file_content(
        self,
        file_paths: list[str],
        show_inode_info=False,
    ):
        """
        Generates the content for the temporary TSV file.
        Returns a mapping of ID to original path and the file content string.
        """
        tips = f"""
            # Lines starting with '#' are ignored.
            # To delete a file, remove its line or comment it out.
            # To create a new file, add a new line with ID 0.
            # To create a new symlink, set the target path in the [args...] position.
            # Note: You cannot 'modify' a symlink, only create a new one.
            # To rename/move a file, edit its path.
            # To swap files, swap their ids.
            # To copy a file, add a new line with the same ID and a different path.
            # Set --copy='ln -nT' to use hard links; set --inode to display hard link information.
            # --- IMPORTANT RULES FOR SPECIAL CHARACTERS ---
            # If your filename contains characters that need to be escaped in the shell,
            # please escape them according to the bash's rules (e.g., add quotes).

            # <ID> <Path> {'<Inode> <Links> ' if show_inode_info else ''}[args...]"""
        tips = dedent(tips[1:])
        lines = [tips]

        nodes = [''] * (len(file_paths) + 1)
        # 0 is the empty path
        for idx, file_path in enumerate(file_paths, 1):
            nodes[idx] = file_path
            cmds = [str(idx), file_path]
            path = Path(file_path)
            # Get inode
            if show_inode_info:
                if path.exists(follow_symlinks=False):
                    stat = path.stat(follow_symlinks=False)
                    inode_info = map(str, (stat.st_ino, stat.st_nlink))
                else:
                    inode_info = [str(None)] * 2
                cmds.extend(inode_info)
            # Get symlink path
            if path.is_symlink():
                cmds.append(str(path.readlink()))
            # Handle special characters in the path.
            lines.append(shlex.join(cmds))

        return nodes, '\n'.join(lines) + '\n'

    def _parse_edited_file(
        self,
        temp_file_path: Path,
        origin_nodes: list[str],
        has_inode_info=False,
    ):
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

                min_len = 4 if has_inode_info else 2
                if len(parts) < min_len:
                    self._console.print(
                        f'[bold red]Error:[/] Malformed line {idx}: {line}'
                    )
                    sys.exit(1)

                if has_inode_info:
                    file_id, new_path, inode, links, *args = parts
                else:
                    file_id, new_path, *args = parts

                file_id = int(file_id)

                if not 0 <= file_id < len(origin_nodes):
                    self._console.print(
                        f'[bold red]Error:[/] Invalid ID {file_id} on line {idx}: {line}'
                    )
                    sys.exit(1)

                original_path = origin_nodes[file_id]
                edges.append((original_path, new_path, {'args': args}))

        return edges

    # [TODO], Star > 1k
    # 1. When id > len(paths), each id can use its own create command.
    # 2. Allow users to use custom command templates and arguments.
    def run(
        self,
        *paths: str,
        editor: str = os.getenv('VISUAL')
        or os.getenv('EDITOR')
        or platform_cmds['code -w'].get(os.name)
        or 'code -w',
        output_script=f'file_ops.{"ps1" if os.name == "nt" else "sh"}',
        edit_suffix='.sh',
        null=False,
        copy: str = platform_cmds['cp -iRT'].get(sys.platform, 'cp -iRT'),
        move: str = platform_cmds['mv -iT'].get(sys.platform, 'mv -iT'),
        exchange: str = '',
        remove: str = platform_cmds['rm -IR'].get(sys.platform, 'rm -IR'),
        create: str = platform_cmds['touch'].get(sys.platform, 'touch'),
        create_args: str = platform_cmds['ln -sinT'].get(sys.platform, 'ln -sinT'),
        # creates=('touch', 'new', 'mkdir -p', '-sinT'),
        move_tmp_filename: str | None = None,
        inode=False,
        cmd_prefix='',
        # cmd_tmpl='{PFX} {CMD} {ARGS} {SRC} {DEST}',
        # copy_tmpl='{PFX} {CMD} {ARGS} {SRC} {DEST}',
        # move_tmpl='{PFX} {CMD} {ARGS} {SRC} {DEST}',
        # exchange_tmpl='{PFX} {CMD} {ARGS} {SRC} {DEST}',
        # remove_tmpl='{PFX} {CMD} {ARGS} {SRC}',
        # create_tmpl='{PFX} {CMD} {ARGS} {DEST}',
        # cmd_token='{CMD}',
        # source_token='{SRC}',
        # target_token='{DEST}',
        # prefix_token='{PFX}',
        # args_token='{ARGS}',
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
        :param move: The command to use for move operations.
        :param exchange: The command to use for atomically swap filenames.
                Currently, only higher versions of Linux support the `mv --exchange -iT` command.
        :param remove: The command to use for remove operations.
        :param create: The command to use for create operations.
        :param create_args: The create command with extra arguments (e.g., for symlinks).
        :param move_tmp_filename: Path for the temporary filename used during cycle move operations.
        :param inode: Whether to display inode and hard link count.
                When adding a new row, the Inode and Links columns must be set to None.
        :param cmd_prefix: An optional command prefix to prepend to all commands.
        """
        # Get input paths
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

        if exchange:
            self._console.print(
                f'[yellow][NOTE]: The {exchange} command will be used to exchange files instead of using temporary files.[/]'
            )

        # Split commands into lists
        cmds = [remove, create, create_args, copy, move, exchange]
        if cmd_prefix:
            cmd_prefix = shlex.split(cmd_prefix, comments=True)
        for i, cmd in enumerate(cmds):
            cmd = shlex.split(cmd, comments=True)
            if cmd_prefix:
                cmd = [*cmd_prefix, *cmd]
            # Update the command in the list
            cmds[i] = cmd
        # Unpack the commands
        remove, create, create_args, copy, move, exchange = cmds

        origin_nodes, temp_content = self._generate_temp_file_content(
            input_paths, show_inode_info=inode
        )

        try:
            # Create a temporary file that we control
            fd, tmp_path_str = tempfile.mkstemp(suffix=edit_suffix, text=True)
            tmp_path = Path(tmp_path_str)
            os.close(fd)

            # Write to the file and then close it to ensure the content is flushed to disk.
            tmp_path.write_text(temp_content)

            # 2. Open in editor
            editor_cmd = self._get_editor(editor)
            edit_cmd = editor_cmd[tmp_path]

            prompt_text = f"""
            Opening temporary file in editor: [green]{tmp_path}[/]
            The running command: [green]{edit_cmd}[/]
            Save and close the editor to continue...
            """
            prompt_text = dedent(prompt_text[1:])
            self._console.print(prompt_text)

            # This call blocks until the editor is closed
            edit_cmd & FG

            self._console.print('[yellow]Editor closed. Processing changes...[/]\n')

            # 3. Parse the results
            edges = self._parse_edited_file(
                tmp_path, origin_nodes, has_inode_info=inode
            )

            # 4. Call the planning algorithm
            ops_gen = GraphOperationGenerator(
                nodes=origin_nodes,
                edges=edges,
                remove=remove,
                move=move,
                exchange=exchange,
                copy=copy,
                create=create,
                create_args=create_args,
            )
            operations = ops_gen.generate_operations(
                tmp_name=move_tmp_filename or f'./__{generate(size=8)}__.tmp',
                is_exchange=bool(exchange),
            )

            # 5. Generate and write script
            self.write_script(output_script, operations)

        finally:
            # 6. Clean up the temporary file
            if 'tmp_path' in locals() and tmp_path and tmp_path.exists():
                tmp_path.unlink()

    def write_script(self, filepath: str | Path, operations: list[list[str]]):
        output_path = Path(filepath)
        header = f"""
        #!/bin/sh
        # Run this script in the same directory where you ran the original command.
        # Example: {'source ' if os.name != 'nt' else '.\\'}{filepath}
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

        output_path.write_text('\n'.join(script_content) + '\n')

        self._console.print(f'Generated script at [green]{output_path}[/]')


def main():
    """Main entry point for the fscode CLI."""
    fscode = FSCode()
    fire.Fire(fscode.run)


if __name__ == '__main__':
    main()
