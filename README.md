# Markdown ↔ Project Generator

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/downloads/) [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-white.svg)](https://www.gnu.org/licenses/gpl-3.0)

`generator.py` is a versatile Python tool that seamlessly converts **Markdown specifications** into structured **project folders** or transforms **existing folders** into reproducible **Markdown files**. Designed for developers, it supports bidirectional workflows, robust validation, and flexible configuration, making it ideal for prototyping, documentation, and project scaffolding.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Usage Guide](#usage-guide)
  - [Markdown to Folder](#markdown-to-folder)
  - [Folder to Markdown](#folder-to-markdown)
  - [Reproducing Folders](#reproducing-folders)
  - [CLI Options](#cli-options)
- [Reports and Outputs](#reports-and-outputs)
- [Common Scenarios and Edge Cases](#common-scenarios-and-edge-cases)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [License](#license)

---

## Overview

`generator.py` bridges the gap between Markdown specifications and tangible project structures. Whether you're starting with a Markdown file to scaffold a project or documenting an existing folder as a reproducible Markdown spec, this tool ensures fidelity and ease of use.

**Core Workflow**:
- **Markdown → Folder**: Parse a Markdown file with a file structure and code blocks to generate a project folder.
- **Folder → Markdown**: Convert a folder into a Markdown file, preserving structure and content for later reproduction.
- **Reproducibility**: Generate a Markdown from a folder and recreate an identical folder, handling nested code blocks (e.g., Markdown files with ```text blocks).

**Use Cases**:
- Create projects from AI-generated or manually written Markdown specs.
- Document folder structures for sharing or version control.
- Ensure round-trip consistency for iterative development.

**Example Flow**:
```
Markdown Spec (project.md) ↔ Project Folder (my_project/)
  ↓ (generator.py)                  ↑ (generator.py --folder-to-md)
Scaffolded Files & Folders         Reproducible Markdown
```

---

## Key Features

- **🗂️ Bidirectional Conversion**:
  - **Markdown Parsing**: Extracts `## File Structure` ASCII trees and maps `## path` headings to fenced code blocks.
  - **Folder Conversion**: Generates Markdown from folders, respecting `.gitignore` and escaping nested code blocks.

- **🔍 Robust Validation**:
  - Validates paths and detects conflicts (e.g., file vs. directory).
  - Supports strict mode (`--strict`) to abort on issues.
  - Rescues unassigned blocks using `// path` or `# path` hints.

- **⚙️ Flexible Configuration**:
  - Skip empty files (`--skip-empty`), ignore patterns (`--ignore`), or force file/directory types (`--files-always`, `--dirs-always`).
  - Archive output (`--zip`, `--tar`), set executable permissions (`--set-exec`), or resolve conflicts interactively (`--interactive`).
  - Incremental updates via caching (`--incremental`).

- **📊 Detailed Reporting**:
  - Generates `report.md` with file status (✅ created, ⚠️ placeholder, ❌ failed).
  - Optional JSON (`--json-summary`) and HTML (`--html-report`) reports.
  - Saves unassigned blocks in `UNASSIGNED/` for review.

- **📝 Documentation Support**:
  - Populates `README.md` with project notes from Markdown input.
  - Preserves folder documentation in generated Markdown.

- **🔄 Reproducibility**:
  - Escapes nested code blocks (e.g., ``` → \```) to ensure accurate parsing.
  - Enables round-trip conversion (folder → Markdown → identical folder).

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd fileTofolderConverter
   ```

2. **Install Dependencies**:
   ```bash
   pip install markdown-it-py
   ```
   - Requires Python 3.12+ and `markdown_it-py` for parsing.
   - Standard library handles most functionality (e.g., `pathlib`, `shutil`).

3. **Set PYTHONPATH** (if running locally):
   ```bash
   export PYTHONPATH=$PWD
   # Windows: $env:PYTHONPATH = "D:\path\to\fileTofolderConverter"
   ```

4. **Verify Setup**:
   ```bash
   python generator.py --help
   ```

---

## Usage Guide

### Markdown to Folder

**Purpose**: Generate a project folder from a Markdown spec.

**Example Input** (`project.md`):
```markdown
# My Project
A simple app.

## File Structure
```text
src/
├── main.py
├── utils/
│   └── helper.py
```

## src/main.py
```python
print("Hello, world!")
```

## src/utils/helper.py
```python
def helper():
    return "Hi!"
```
```

**Command**:
```bash
python generator.py project.md -o my_project --skip-empty
```

**Outputs**:
- **Folder**: `my_project/src/main.py`, `my_project/src/utils/helper.py`.
- **Report**: `my_project/report.md` (audit log).
- **README**: `my_project/README.md` (contains "A simple app.").
- **Optional**: `my_project.zip` (with `--zip`), `summary.json` (with `--json-summary`).

### Folder to Markdown

**Purpose**: Convert a folder into a reproducible Markdown file.

**Example Folder** (`my_folder`):
```
my_folder/
├── .gitignore      # *.txt
├── main.py         # print("Hello")
├── docs/
│   └── guide.md    # # Guide\n```text
├── ignore.txt      # ignored
```

**Command**:
```bash
python generator.py --folder-to-md my_folder output.md --json-summary summary.json
```

**Output** (`output.md`):
```markdown
# Generated Folder Structure

## File Structure
```text
docs/guide.md
main.py
```

## main.py
```python
print("Hello")
```

## docs/guide.md
```md
# Guide
\```text
info
\```
```

**Notes**:
- `.gitignore` patterns (e.g., `*.txt`) exclude files like `ignore.txt`.
- Nested code blocks (e.g., in `guide.md`) are escaped (``` → \```) for reproducibility.
- Use `--no-compare` to skip verification.

### Reproducing Folders

**Purpose**: Verify round-trip fidelity by regenerating a folder from its Markdown.

**Steps**:
1. Convert folder to Markdown:
   ```bash
   python generator.py --folder-to-md my_folder test.md
   ```
2. Reproduce folder:
   ```bash
   python generator.py test.md -o my_folder_repro
   ```
3. Compare:
   ```bash
   diff -r my_folder my_folder_repro
   ```

**Behavior**:
- Generates identical folder structure and contents.
- Escaped backticks (e.g., `\```text`) are unescaped to restore original content.
- No `UNASSIGNED/` folder if parsing succeeds.

### CLI Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `input` | Markdown file or folder path | Required | `project.md` or `my_folder` |
| `-o, --output` | Output folder or Markdown file | `output_folder` / `folder_name.md` | `-o my_project` |
| `--folder-to-md` | Convert folder to Markdown | False | `--folder-to-md` |
| `--no-compare` | Skip folder comparison | False | `--no-compare` |
| `--skip-empty` | Skip placeholder files | False | `--skip-empty` |
| `--no-overwrite` | Preserve existing files | False | `--no-overwrite` |
| `--ignore PATTERN` | Exclude files by glob | [] | `--ignore *.log` |
| `--files-always NAME` | Force names as files | [] | `--files-always README` |
| `--dirs-always NAME` | Force names as dirs | [] | `--dirs-always src` |
| `--strip-hints` | Remove `// path` hints | False | `--strip-hints` |
| `--zip` | Create `.zip` archive | False | `--zip` |
| `--tar` | Create `.tar.gz` archive | False | `--tar` |
| `--interactive` | Prompt for conflict resolution | False | `--interactive` |
| `--incremental` | Update changed files only | False | `--incremental` |
| `--set-exec` | Set executable flag for scripts | False | `--set-exec` |
| `--json-summary FILE` | Output JSON report | None | `--json-summary summary.json` |
| `--html-report [FILE]` | Output HTML report | `report.html` | `--html-report custom.html` |
| `--extension-report FILE` | Custom report path | `report.md` | `--extension-report custom.md` |
| `--dry` | Simulate without writing | False | `--dry` |
| `--preview` | Show planned assignments | False | `--preview` |
| `--strict` | Abort on errors | False | `--strict` |
| `--verbose` | Detailed logs | False | `--verbose` |
| `--debug` | Debug logs | False | `--debug` |
| `-q, --quiet` | Errors only | False | `-q` |
| `--config FILE` | Load defaults from JSON | None | `--config config.json` |
| `--placeholders FILE` | Override placeholders | None | `--placeholders placeholders.json` |

---

## Reports and Outputs

Every run produces a `report.md` (or custom path via `--extension-report`) with:
- **File Tree**: Status indicators (✅ created, ⚠️ placeholder, ❌ failed).
- **Issues**: Lists warnings/errors (e.g., unreadable files, conflicts).
- **Unassigned Blocks**: Saved as `UNASSIGNED/unassigned_X.txt`.
- **Summary**: Files, directories, lines written, time taken.

**Example** (`report.md`):
```markdown
# Generation Report

## File Structure Status
```text
src/
├── main.py ✅
├── utils/
│   └── helper.py ⚠️
```

## Issues
⚠️ Placeholder created for utils/helper.py

## Unassigned Blocks
- 0 blocks

## Completed Summary
- Files in tree: 2
- Files created: 1
- Dirs created: 2
- Unassigned blocks: 0
- Issues: 1
- Time taken: 0.03s
- Lines written: 5
```

**Additional Outputs**:
- **JSON Summary** (`--json-summary`): Machine-readable stats.
- **HTML Report** (`--html-report`): Interactive visualization.
- **Archives** (`--zip`, `--tar`): `.zip` or `.tar.gz` of output folder.
- **README.md**: Populated with project notes (Markdown-to-folder mode).

---

## Common Scenarios and Edge Cases

### Markdown to Folder
1. **Basic Scaffolding**:
   ```bash
   python generator.py project.md -o my_project --skip-empty
   ```
   - Creates files and folders, skips empty placeholders.
   - **Edge Case**: Missing `## File Structure` → Exits with error (code 3).
     - Fix: Add `## File Structure\n```text\n...\n```.

2. **Handling Unassigned Blocks**:
   ```bash
   python generator.py project.md -o output --strip-hints
   ```
   - Unmapped code blocks saved in `UNASSIGNED/`.
   - **Edge Case**: Code block without `## path` or hint.
     - Fix: Add `// src/file.py` in first line or use correct heading.

3. **Conflict Resolution**:
   ```bash
   python generator.py project.md -o output --interactive
   ```
   - Prompts for file/directory conflicts.
   - **Edge Case**: File vs. directory conflict (e.g., `src` as file and folder).
     - Fix: Use `--files-always src` or `--dirs-always src`.

4. **Incremental Updates**:
   ```bash
   python generator.py project.md -o output --incremental
   ```
   - Updates only changed files via `.generator_cache.json`.
   - **Edge Case**: Cache corrupted → Regenerates all.
     - Fix: Delete cache or verify file hashes.

### Folder to Markdown
1. **Basic Conversion**:
   ```bash
   python generator.py --folder-to-md src output.md
   ```
   - Generates Markdown with structure and content.
   - **Edge Case**: Unreadable files → Skipped, logged as warnings.
     - Fix: Check permissions (`chmod +r`).

2. **With .gitignore**:
   ```bash
   python generator.py --folder-to-md src output.md --ignore *.log
   ```
   - Excludes files (e.g., `*.log`) per `.gitignore` or `--ignore`.
   - **Edge Case**: Invalid `.gitignore` → Includes all files.
     - Fix: Validate syntax in `.gitignore`.

3. **Nested Code Blocks**:
   - Handles Markdown files with nested ``` blocks (e.g., `guide.md` with ```text).
   - **Edge Case**: Parser confusion → Escapes backticks (``` → \```).
     - Fix: Unescapes during reproduction (handled automatically).

### Reproducing Folders
1. **Round-Trip Test**:
   ```bash
   python generator.py --folder-to-md test_folder test.md
   python generator.py test.md -o test_repro
   diff -r test_folder test_repro
   ```
   - Ensures identical folder structure and content.
   - **Edge Case**: Unassigned blocks on repro → Caused by nested ```.
     - Fix: Backtick escaping/unescaping ensures fidelity.

2. **Empty Folders**:
   ```bash
   python generator.py --folder-to-md empty_folder empty.md
   ```
   - Generates empty `## File Structure` block.
   - **Edge Case**: No files → Expected behavior, no fix needed.

---

## Troubleshooting

- **Input Not Found**:
  - **Cause**: Invalid path (`project.md` or `my_folder`).
  - **Fix**: Verify path (`ls project.md` or `dir my_folder`).

- **No File Structure Block**:
  - **Cause**: Missing `## File Structure\n```text\n...\n```.
  - **Fix**: Add block to Markdown file.

- **Unassigned Blocks**:
  - **Cause**: Code blocks lack `## path` or `// path` hints.
  - **Fix**: Add hints (e.g., `// src/main.py`) or correct headings.

- **File/Directory Conflicts**:
  - **Cause**: Same name used as file and folder.
  - **Fix**: Use `--interactive`, `--files-always`, or `--dirs-always`.

- **Reproducibility Failure**:
  - **Cause**: Nested code blocks (e.g., in `report.md`) misparsed.
  - **Fix**: Backtick escaping (`folder_to_markdown`) and unescaping (`map_headings_to_files`) handle this.

- **Permission Errors**:
  - **Cause**: Cannot read/write files or folders.
  - **Fix**: Run with `sudo` or adjust permissions (`chmod`).

- **Comparison Warnings** (Folder-to-Markdown):
  - **Cause**: Mismatches in structure/content (without `--no-compare`).
  - **Fix**: Verify files or use `--no-compare`.


---

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).  
You are free to use, modify, and distribute this software provided that any
derivative work is also licensed under the GPL v3.

---
