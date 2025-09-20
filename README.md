
# FSCode: Batch File Operations in Your Editor

FSCode is a command-line tool that allows you to perform batch file operations (move, copy, delete) on a list of file paths using the comfort and power of your favorite text editor.

It works by taking a list of files, opening them in a temporary file for you to edit, and then generating a shell script to apply your changes. This approach is ideal for complex renaming, restructuring, or cleaning up of files where multi-cursor editing and other advanced editor features can save a significant amount of time.

## Features

* **Editor-Based Operations**: Edit file paths in a temporary file to define move, copy, and delete actions.
* **Flexible Input**: Accepts file paths directly as command-line arguments or piped from other commands like `find`, `ls`, or `fd`.
* **Safe Execution**: Generates an executable shell script with the planned operations. This allows you to review the commands before running them.
* **Handles Special Characters**: Correctly processes file paths with spaces, quotes, and other special characters.
* **Smart Operation Planning**:
    * Correctly handles complex move cycles (e.g., renaming `a` to `b` and `b` to `a`) by using a temporary file or an atomic exchange operation.
* **Customizable**: Configure your preferred editor, output script name, and the underlying `mv`, `cp`, and `rm` commands.

## How It Works

1.  **Input**: You provide a list of file paths to `fscode`.
2.  **Edit**: `fscode` generates a temporary TSV file where each line contains a unique ID and a file path. Lines starting with '#' are comments. This file is automatically opened in your configured text editor (e.g., VS Code, Vim).
3.  **Generate**: Once you save and close the editor, `fscode` parses your changes and generates a shell script (`file_ops.fish` by default) containing the necessary `mv`, `cp`, and `rm` commands to achieve the desired state.
4.  **Execute**: You can then review and run the generated script to apply the changes.

## Installation

### Prerequisites

* Python 3.x
* A command-line text editor configured (the tool defaults to using the `$VISUAL` or `$EDITOR` environment variables, or `code -w` as a fallback).

### Dependencies

The script relies on the following Python libraries:

* `fire`: For creating the command-line interface.
* `plumbum`: For running external commands.
* `rich`: For formatted console output.
* `networkx`: For graph manipulation and analysis.

You can install them using pip:

```fish
pip install fscode
# or
pip install -e .
```

## Usage

### Basic Example

Let's say you have the following files:

```fish
report-final.txt
summary_v1.txt
```

Run `fscode` with these paths:

```fish
fscode report-final.txt summary_v1.txt
```

Your editor will open a temporary file with the following content:

```fish
# File Operation Plan,
# Format: <ID>	<Path>,
# Lines starting with '#' are ignored.",
# To delete a file, remove its line or comment it out.,
# To rename/move a file, edit its path.,
# To copy a file, add a new line with the same ID and a different path.,
# --- IMPORTANT RULES FOR SPECIAL CHARACTERS ---,
# If your content contains a double quote ("), you MUST type it as \",
# If your content contains a backslash (\), you MUST type it as \\,
# If your content contains a tab (\t), you MUST type it as \t,
# If your content contains a newline (\n), you MUST type it as \n,
# --------------------------------------------------
1	report-final.txt
2	summary_v1.txt
```

Now, let's make some changes:

  * Rename `report-final.txt` to `report.txt`.
  * Delete `summary_v1.txt`.
  * Copy `report.txt` to `archive/report_backup.txt`.

You would edit the file to look like this:

```fish
# ... (header comments)
1	report.txt
# 2	summary_v1.txt  <-- This line is commented out to delete the file
1	archive/report_backup.txt <-- This new line copies from original ID 1
```

After you save and close the editor, `fscode` will generate a `file_ops.fish` script:

```fish
#!/bin/fish
# Run with `source <output_script>`, the current directory location must be the same.
mv report-final.txt report.txt
cp report.txt archive/report_backup.txt
rm summary_v1.txt
```

You can now review this script and run it to apply the changes:

```fish
source file_ops.fish
```

### Using with Other Commands (Piping)

`fscode` also accepts input from stdin, which makes it powerful when combined with tools like `find`.

```fish
# Find all .jpeg files and prepare them for renaming
find . -type f -name "*.jpeg" | fscode
```

## Command-Line Options

The behavior of `fscode` can be modified with the following command-line arguments:

| Argument             | Description                                                                     | Default                              |
| -------------------- | ------------------------------------------------------------------------------- | ------------------------------------ |
| `*paths`             | File paths to process. Can be provided as arguments or via stdin.               | N/A                                  |
| `--editor`           | The editor command to use.                                                      | `$VISUAL`, `$EDITOR`, or `'code -w'` |
| `--output_script`    | Path to write the generated shell script.                                       | `file_ops.fish`                      |
| `--rm`               | The command to use for remove operations.                                       | `'rm'`                               |
| `--cp`               | The command to use for copy operations.                                         | `'cp'`                               |
| `--mv`               | The command to use for move operations.                                         | `'mv'`                               |
| `--exchange`         | Use an exchange-based move for cycles, avoiding temporary files.                | `False`                              |
| `--mv_exchange`      | The command for atomic swap/exchange moves (used if `--exchange` is true).      | `'mv --exchange'`                    |
| `--cmd_prefix`       | An optional command prefix to prepend to all commands (e.g., `sudo`).           | `None`                               |
| `--mv_temp_filename` | Path for the temporary file used during move cycles when `--exchange` is false. | `'./__mv_tmp'`                       |
| `--edit_suffix`      | Suffix for the temporary editing file.                                          | `'.fish'`                            |

Example with custom options:

```fish
# Use vim as the editor and output a fish script
find . -name "*.tmp" | fscode --editor "vim" --output_script "cleanup.fish"
```
