# 🧩 FSCode (Filename Studio Code) — 用你的编辑器管理文件

[![English](https://img.shields.io/badge/English-blue.svg?style=flat-square)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-brightgreen.svg?style=flat-square)](README.zh.md)

[![PyPI](https://img.shields.io/badge/pypi-PyFSCode-blue.svg)](https://pypi.org/project/fscode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-default.svg)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/github/stars/bit0r/fscode)](https://github.com/Bit0r/fscode)

> 把你的 VS Code / Vim 变成文件操作 IDE。
> 从“可视化清单”生成安全可审查的批处理脚本（重命名/删除/创建/复制/软链接等）。

## 🏁 快速开始

```bash
pip install PyFSCode
find ./photos -name "*.jpg" | fscode --editor='code -w' *.txt
```

## ⚡️ 视频演示

![演示视频](https://github.com/user-attachments/assets/3edaedec-8364-4a43-9050-cf7fd0f3a8dd)

## 🤔 为什么会有这个工具？

批量文件操作（重命名/删除/复制/创建/软链接）是命令行世界最常见但最易出错的任务：

- `mv`, `rm`, `cp`, `touch`, `ln`, `ln -s` 命令对于**批量**操作非常笨拙且容易出错。
- 手写 `for` 循环和 `sed` 来重命名，心智负担很重。
- **交换文件名**非常复杂，甚至在GUI下都无法完成操作。

`fscode` 提供了一个更强大、更统一的解决方案。

## 🚀 它能做什么？

`fscode` 让你用编辑器批量规划文件操作，并安全生成脚本执行。

## ✨ 核心功能

- 💻 **编辑器即 UI** — 用 VS Code/Vim 的强大功能（多光标、正则、宏）管理文件；
- 🧠 **智能依赖处理** — 自动解决交换、循环、移动冲突；
- 🛡️ **安全可控** — 不直接修改文件，只生成一个可审查的文件操作脚本；
- 🧰 **全功能支持** — 创建、复制、移动、删除、重命名、软链接都支持。
- 🎨 **自定义命令** - 例如，你可以使用 `ai-generate` 替换 `touch`，创建有内容的文件。
- 🏷️ **自定义命令前缀** - 例如，你可以将 `sudo` 作为输出脚本的前缀。

# 📦 安装

```bash
pip install PyFSCode
# 或使用 uv
uv tool install PyFSCode
```

# 🧑‍💻 使用示例

## 💻 第1步-命令行输入文件

⚠️ [NOTE]：如果你的环境变量 `$VISUAL` 或 `$EDITOR` 指向 VS Code，请使用 `--editor='code -w'` 以等待窗口关闭再继续。

### 方式1：从管道输入

```bash
find ./photos -name "*.jpg" | fscode
```

### 方式2：直接传参

```bash
fscode *.jpg *.txt
```

### 方式3：管道+传参

```bash
find ./photos -name "*.jpg" | fscode *.jpg *.txt
```

### 方式4：使用自定义命令操作（高级用户）

```bash
fscode --is_exchange --inode --editor='code -w' --create='new' --remove='del' --move='mov' **
```

## 📄 第2步-编辑器内修改文件名

编辑器会打开一个类似的文件：

```sh
# <ID> <Path> [args...]
1 photos/vacation.jpg
2 photos/birthday.jpg
3 project/notes.txt
4 "photos/old picture.jpg"
```

你只需修改它：

```sh
# 文件操作计划
# ... (省略注释) ...
#
# 我的修改

# 1. 重命名 (编辑路径)
1 photos/Paris_Vacation_2025.jpg

# 2. 移动 (编辑路径)
3 archive/old_notes.txt

# 3. 复制 (复制行，使用相同 ID 2)
2 photos/birthday.jpg
2 photos/backup_birthday.jpg

# 4. 删除 (删除或注释 ID 4 对应的行)
# 4 "photos/old picture.jpg"

# 5. 创建 (添加新行，ID 为 0，因为有空格所以需要使用引号)
0 'new_project/new note.txt'

# 6. 创建符号链接
0 note.txt 'new_project/new note.txt'
```

## ⚡ 第3步: 执行

保存并关闭后编辑器，FSCode会生成脚本：

```bash
#!/bin/sh
cp photos/birthday.jpg photos/backup_birthday.jpg
mv photos/vacation.jpg photos/Paris_Vacation_2025.jpg
mv project/notes.txt archive/old_notes.txt
rm 'photos/old picture.jpg'
touch 'new_project/new note.jpg'
ln -snT 'new_project/new note.txt' note.txt
```

审查无误后，执行它：

```bash
source ./file_ops.sh
```

✅ 所有变更在执行前都可安全审查。

# 📄 帮助文档

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

# 🌈 其它推荐工具

- [human-utils](https://github.com/xixixao/human-utils)
- [fd](https://github.com/sharkdp/fd)

## 🐟 fish 脚本 alias 示例

```sh
alias -s fscode "fscode --is_exchange --editor='code -w' --create='new' --remove='del' --move='mov'"
```

## 🪶 提示

- 要想使用硬链接，可以用 `--inode` 开启硬链接信息显示。使用 `--cp='ln -snT'` 替换 `cp` 操作
- 要想使用软链接，可以修改 `[args...]` 列，同时将ID设为0，`fscode`将自动使用`create_args`创建。如果需要强制创建进行覆盖，则需要手动修改`--create_args='ln -snTf'`。目前仅“创建”功能支持自定义参数，星标⭐超过1000将考虑为所有应用增加自定义参数。
- 要想使用 `sudo`，可以设置 `--cmd_prefix=sudo`，这将在所有命令前添加前缀。

## 🔗 功能对比

|       工具       | ✅数量  | 跨编辑器 | 交互式 | 输出脚本 | 自定义命令 | 移动  | 交换/环 | 复制  | 删除  | 创建  |         软链接         |         硬链接         |
| :--------------: | :----: | :------: | :----: | :------: | :--------: | :---: | :-----: | :---: | :---: | :---: | :--------------------: | :--------------------: |
|    [edir][1]     |   5    |    ✅     |   ❌    |    ❌     |     ❌      |   ✅   |    ✅    |   ✅   |   ✅   |   ❌   |           ❌            |           ❌            |
| [renameutils][2] |   5    |    ✅     |   ❌    |    ❌     |     ✅      |   ✅   |    ✅    |   ✅   |   ❌   |   ❌   |           ❌            |           ❌            |
| [pipe-rename][3] |   3    |    ✅     |   ❌    |    ❌     |     ❌      |   ✅   |    ✅    |   ❌   |   ❌   |   ❌   |           ❌            |           ❌            |
|   [massren][4]   |   4    |    ✅     |   ❌    |    ❌     |     ❌      |   ✅   |    ✅    |   ❌   |   ✅   |   ❌   |           ❌            |           ❌            |
|    [dired][5]    |   9    |    ❌     |   ✅    |    ❌     |     ✅      |   ✅   |    ✅    |   ✅   |   ✅   |   ✅   |           ✅            |           ✅            |
|    [acme][6]     |   8    |    ❌     |   ✅    |    ❌     |     ✅      |   ✅   |    ❌    |   ✅   |   ✅   |   ✅   | ✅<sup>[1](#注意)</sup> | ✅<sup>[1](#注意)</sup> |
|     [up][7]      |   3    |    ❌     |   ✅    |    ✅     |     ✅      |   ❌   |    ❌    |   ❌   |   ❌   |   ❌   |           ❌            |           ❌            |
|      fscode      | **10** |    ✅     |   ❌    |    ✅     |     ✅      |   ✅   |    ✅    |   ✅   |   ✅   |   ✅   |           ✅            | ✅<sup>[2](#注意)</sup> |

###### 注意

1. 由于plan9的特性，该系统并不使用“链接”，而是“[绑定](https://en.wikipedia.org/wiki/Plan_9_from_Bell_Labs#Union_directories_and_namespaces)”
2. 只需要设置`--copy='ln -nTf'`和`--inode`，那么就能像普通复制一样处理硬链接

[1]: https://github.com/bulletmark/edir
[2]: https://www.nongnu.org/renameutils/
[3]: https://github.com/marcusbuffett/pipe-rename
[4]: https://github.com/laurent22/massren
[5]: https://www.gnu.org/software/emacs/manual/html_node/emacs/Dired.html
[6]: https://9p.io/sys/doc/acme/acme.html
[7]: https://github.com/akavel/up

# 附录

## 📄 许可

本项目基于 [MIT License](LICENSE.txt) 开源。

## 🪶 小贴士

> 喜欢这个项目？请给它一个 ⭐️ Star。
> 你的支持能让更多人发现它。
