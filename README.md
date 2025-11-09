# 🧩 FSCode (Filename Studio Code) — Manage Your Filesystem with Your Editor

[![English](https://img.shields.io/badge/English-blue.svg?style=flat-square)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-brightgreen.svg?style=flat-square)](README.zh.md)

[![PyPI](https://img.shields.io/badge/pypi-PyFSCode-blue.svg)](https://pypi.org/project/fscode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-default.svg)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/github/stars/bit0r/fscode)](https://github.com/Bit0r/fscode)

> Turn your VS Code / Vim into a file operations IDE.
> Generate safe, reviewable batch scripts (rename/delete/create/copy/symlink, etc.) from a "visual manifest".

## 🏁 Quick Start

```bash
pip install PyFSCode
find ./photos -name "*.jpg" | fscode --editor='code -w' *.txt
```

## ⚡️ Video Demo

[Video Demo](https://github.com/user-attachments/assets/3edaedec-8364-4a43-9050-cf7fd0f3a8dd)

## 🤔 Why This Tool?

Batch file operations (rename / delete / create / copy / symlink) are the most common yet error-prone tasks in the command-line world:

- `mv`, `rm`, `cp`, `touch`, `ln`, `ln -s` commands are very clumsy and error-prone for **batch** operations.
- Manually writing `for` loops and `sed` for renaming carries a heavy mental load.
- **Swapping filenames** is very complex and often impossible even in a GUI.

`fscode` provides a more powerful and unified solution.

## 🚀 What Can It Do?

`fscode` lets you use your editor to plan batch file operations and safely generate a script for execution.

## ✨ Core Features

- 💻 **Editor as UI** — Use the powerful features of VS Code/Vim (multi-cursor, regex, macros) to manage files;
- 🧠 **Smart Dependency Handling** — Automatically resolves swap, cycle, and move conflicts;
- 🛡️ **Safe and Controllable** — Does not modify files directly, only generates a reviewable file operation script;
- 🧰 **Full Features Support** — Supports creation, copying, moving, deleting, renaming and Symlink.
- 🎨 **Custom Commands** - For example, you can replace `touch` with `ai-generate` to create files with content.
- 🏷️ **Custom Command Prefix** - For example, you can use `sudo` as a prefix for the output script.

# 📦 Installation

```bash
pip install PyFSCode
# Or using uv
uv tool install PyFSCode
```

# 🧑‍💻 Usage Example

## 💻 Step 1: Input Files from Command Line

⚠️ [NOTE]: If your `$VISUAL` or `$EDITOR` environment variable points to VS Code, please use `--editor='code -w'` to wait for the window to close before continuing.

### Method 1: Input from Pipe

```bash
find ./photos -name "*.jpg" | fscode
```

### Method 2: Pass as Arguments

```bash
fscode *.jpg *.txt
```

### Method 3: Pipe + Arguments

```bash
find ./photos -name "*.jpg" | fscode *.jpg *.txt
```

### Method 4: Use Custom Commands (Advanced Users)

```bash
fscode --is_exchange --inode --editor='code -w' --create='new' --remove='del' --move='mov' **
```

## 📄 Step 2: Modify Filenames in the Editor

The editor will open a file similar to this:

```sh
# <ID> <Path> [args...]
1 photos/vacation.jpg
2 photos/birthday.jpg
3 project/notes.txt
4 "photos/old picture.jpg"
```

You just need to modify it:

```sh
# File Operation Plan
# ... (comments omitted) ...
#
# My Modifications

# 1. Rename (Edit the path)
1 photos/Paris_Vacation_2025.jpg

# 2. Move (Edit the path)
3 archive/old_notes.txt

# 3. Copy (Duplicate the line, use the same ID 2)
2 photos/birthday.jpg
2 photos/backup_birthday.jpg

# 4. Delete (Delete or comment out the line with ID 4)
# 4 "photos/old picture.jpg"

# 5. Create (Add a new line, ID is 0, quotes are needed due to spaces)
0 'new_project/new note.txt'

# 6. 创建符号链接
0 note.txt 'new_project/new note.txt'
```

## ⚡ Step 3: Execute

After saving and closing the editor, FSCode will generate a script:

```bash
#!/bin/sh
cp photos/birthday.jpg photos/backup_birthday.jpg
mv photos/vacation.jpg photos/Paris_Vacation_2025.jpg
mv project/notes.txt archive/old_notes.txt
rm 'photos/old picture.jpg'
touch 'new_project/new note.jpg'
ln -snT 'new_project/new note.txt' note.txt
```

After reviewing it for correctness, execute it:

```bash
source ./file_ops.sh
```

✅ All changes can be safely reviewed before execution.

# 📄 Help Documentation

```
INFO: Showing help with the command 'fscode -- --help'.

NAME
    fscode - Main execution flow.

SYNOPSIS
    fscode <flags> [PATHS]...

DESCRIPTION
    Main execution flow.

POSITIONAL ARGUMENTS
    PATHS
        Type: str
        File paths to process. Can be provided as arguments or via stdin.

FLAGS
    --editor=EDITOR
        Type: str
        Default: 'code'
        The editor command to use (e.g., "msedit", "code -w"). Defaults to $VISUAL, $EDITOR, or 'code -w'.
    -o, --output_script=OUTPUT_SCRIPT
        Type: str | pathlib._local.Path
        Default: 'file_ops.sh'
        Path to write the generated shell script.
    --edit_suffix=EDIT_SUFFIX
        Default: '.sh'
        Suffix for the temporary editing file. Defaults to '.sh'.
    -n, --null=NULL
        Default: False
        Whether to use null-separated input.
    --copy=COPY
        Default: 'cp'
        The command to use for copy operations.
    --move=MOVE
        Default: 'mv'
        The command to use for move operations.
    --exchange=EXCHANGE
        Default: 'mv --exchange'
        The command to atomically swap filenames. If you modify to a custom command, is_exchange is automatically enabled.
    -r, --remove=REMOVE
        Default: 'rm'
        The command to use for remove operations.
    --create=CREATE
        Default: 'touch'
        The command to use for create operations.
    --create_args=CREATE_ARGS
        Default: 'ln -snT'
        The create command with extra arguments (e.g., for symlinks).
    --move_tmp_filename=MOVE_TMP_FILENAME
        Type: Optional[str | None]
        Default: None
        Path for the temporary filename used during cycle move operations.
    --is_exchange=IS_EXCHANGE
        Default: False
        Use swap for circular moves and avoid using temporary files. Currently only higher versions of linux are supported.
    --inode=INODE
        Default: False
        Whether to display inode and hard link count. When adding a new row, the Inode and Links columns must be set to None.
    --cmd_prefix=CMD_PREFIX
        Type: Optional[str | None]
        Default: None
        An optional command prefix to prepend to all commands.
```

# 🌈 Other Recommended Tools

- [human-utils](https://github.com/xixixao/human-utils)
- [fd](https://github.com/sharkdp/fd)

## 🐟 fish alias example

```sh
alias -s fscode "fscode --is_exchange --editor='code -w' --create='new' --remove='del' --move='mov'"
```

## 🪶 Tips

- To use hard links, you can use `--inode` to display hard link information. Use `--cp='ln -snT'` to replace the cp operation.
- To use soft links, you can modify the `[args...]` column and set the ID to 0; fscode will then automatically use create_args to create them. If you need to force-create and overwrite, you must manually change `--create_args='ln -snTf'`. Currently, only the "create" function supports custom arguments. If the project gets over 1000 stars ⭐, we will consider adding custom arguments for all operations.
- To use `sudo`, you can set `--cmd_prefix=sudo`, which will add this prefix to all commands.

## 🔗 Feature Comparison

|       Tool       | ✅Count | Cross-editor | Interactive | Output Script | Custom Commands | Move  | Swap/Ring | Copy  | Delete | Create |        Symlink         |        Hardlink        |
| :--------------: | :----: | :----------: | :---------: | :-----------: | :-------------: | :---: | :-------: | :---: | :----: | :----: | :--------------------: | :--------------------: |
|    [edir][1]     |   5    |      ✅       |      ❌      |       ❌       |        ❌        |   ✅   |     ✅     |   ✅   |   ✅    |   ❌    |           ❌            |           ❌            |
| [renameutils][2] |   5    |      ✅       |      ❌      |       ❌       |        ✅        |   ✅   |     ✅     |   ✅   |   ❌    |   ❌    |           ❌            |           ❌            |
| [pipe-rename][3] |   3    |      ✅       |      ❌      |       ❌       |        ❌        |   ✅   |     ✅     |   ❌   |   ❌    |   ❌    |           ❌            |           ❌            |
|   [massren][4]   |   4    |      ✅       |      ❌      |       ❌       |        ❌        |   ✅   |     ✅     |   ❌   |   ✅    |   ❌    |           ❌            |           ❌            |
|    [dired][5]    |   9    |      ❌       |      ✅      |       ❌       |        ✅        |   ✅   |     ✅     |   ✅   |   ✅    |   ✅    |           ✅            |           ✅            |
|    [acme][6]     |   8    |      ❌       |      ✅      |       ❌       |        ✅        |   ✅   |     ❌     |   ✅   |   ✅    |   ✅    | ✅<sup>[1](#Note)</sup> | ✅<sup>[1](#Note)</sup> |
|     [up][7]      |   3    |      ❌       |      ✅      |       ✅       |        ✅        |   ❌   |     ❌     |   ❌   |   ❌    |   ❌    |           ❌            |           ❌            |
|      fscode      | **10** |      ✅       |      ❌      |       ✅       |        ✅        |   ✅   |     ✅     |   ✅   |   ✅    |   ✅    |           ✅            | ✅<sup>[2](#Note)</sup> |

###### Note

1. Due to the nature of Plan 9, the system doesn't use "link" but rather "[bind](https://en.wikipedia.org/wiki/Plan_9_from_Bell_Labs#Union_directories_and_namespaces)".
2. Just set --copy='ln -nTf' and --inode, and you can handle hard links just like regular copying.

[1]: https://github.com/bulletmark/edir
[2]: https://www.nongnu.org/renameutils/
[3]: https://github.com/marcusbuffett/pipe-rename
[4]: https://github.com/laurent22/massren
[5]: https://www.gnu.org/software/emacs/manual/html_node/emacs/Dired.html
[6]: https://9p.io/sys/doc/acme/acme.html
[7]: https://github.com/akavel/up

# Appendix

## 📄 License

This project is open-sourced under the [MIT License](LICENSE.txt).

## 🪶 Tips

> Like this project? Please give it a ⭐️ Star.
> Your support helps more people discover it.
