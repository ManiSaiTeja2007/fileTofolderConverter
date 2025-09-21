# Markdown ↔ Project Generator

`generator.py` is a powerful Python utility that converts a **Markdown specification** into a fully scaffolded **project folder** or transforms an existing **folder** into a reproducible **Markdown file**. It supports bidirectional conversion, robust validation, and flexible configuration for developers and teams building or documenting project structures.

---

## ✨ Features

- **Markdown-to-Folder Conversion**:
  - Parses `## File Structure` ASCII tree to create directories and files.
  - Maps VS Code-style headings (e.g., `## file.py`) to fenced code blocks for file contents.
  - Supports rescue mechanisms for unassigned code blocks using `// file/path` or `# file/path` hints.
  - Validates file paths, detects conflicts, and supports strict enforcement (`--strict`).

- **Folder-to-Markdown Conversion**:
  - Converts a folder into a Markdown file (`--folder-to-md`), respecting `.gitignore` patterns.
  - Generates a reproducible Markdown with `## File Structure` and file contents under `## path` headings.
  - Escapes nested code blocks to ensure accurate parsing when regenerating the folder.
  - Optional comparison (`--no-compare`) to verify the generated structure against the original folder.

- **Configurable Options**:
  - Skip empty files (`--skip-empty`).
  - Ignore patterns (`--ignore *.test.*`).
  - Force names as files or directories (`--files-always`, `--dirs-always`).
  - Strip rescue hints (`--strip-hints`).
  - Archive output (`--zip`, `--tar`).
  - Interactive conflict resolution (`--interactive`).
  - Incremental updates with caching (`--incremental`).
  - Set executable permissions (`--set-exec`).

- **Comprehensive Reporting**:
  - Generates `report.md` with file status (✅ ok, ⚠️ placeholder, ❌ missing).
  - Optional JSON summary (`--json-summary`).
  - HTML report for interactive analysis (`--html-report`).
  - Logs warnings for unassigned blocks, ambiguous hints, or file conflicts.

- **Documentation Support**:
  - Extracts intro/system notes from Markdown to populate `README.md` in the generated project.
  - Preserves folder documentation in Markdown output for `--folder-to-md`.

---

## 🚀 Quickstart

### Markdown-to-Folder
1. Create a Markdown spec (`project.md`):
   ```markdown
   # My Project

   ## File Structure
   ```text
   src/
   ├── main.py
   ├── utils/
   │   ├── helper.py
   ```

   ## src/main.py
   ```python
   print("Hello, world!")
   ```

   ## src/utils/helper.py
   ```python
   def greet():
       return "Hi!"
   ```
   ```

2. Run the generator:
   ```bash
   python generator.py project.md -o my_project --skip-empty
   ```

3. Check results:
   - Folder: `my_project/src/main.py`, `my_project/src/utils/helper.py`
   - Report: `my_project/report.md`
   - Optional: `my_project.zip` (if `--zip` used), `summary.json` (if `--json-summary` used)

### Folder-to-Markdown
1. Prepare a folder (`my_folder`):
   ```
   my_folder/
   ├── .gitignore  # *.txt
   ├── main.py     # print("Hello")
   ├── docs/
   │   ├── readme.md  # # Docs\n```text
   ```

2. Run the generator:
   ```bash
   python generator.py --folder-to-md my_folder output.md
   ```

3. Check results:
   - Markdown file: `output.md` with file structure and contents.
   - Example `output.md`:
     ```markdown
     # Generated Folder Structure
     ## File Structure
     ```text
     docs/readme.md
     main.py
     ```

     ## main.py
     ```python
     print("Hello")
     ```

     ## docs/readme.md
     ```md
     # Docs
     \```text
     info
     \```
     ```
     ```

4. Reproduce folder from Markdown:
   ```bash
   python generator.py output.md -o my_folder_repro
   ```
   - Verifies identical structure (use `diff -r my_folder my_folder_repro`).

---

## 📊 Reports

Each run generates a detailed **report** in `report.md` (or custom path via `--extension-report`):
- **File Tree**: Lists files with status:
  - ✅ Created successfully.
  - ⚠️ Placeholder (empty content, unless `--skip-empty`).
  - ❌ Missing or failed to create.
- **Warnings/Errors**: Notes on parsing issues, unassigned blocks, or conflicts.
- **Unassigned Blocks**: Saved in `UNASSIGNED/` folder if present.
- **Summary**: Counts of files, directories, unassigned blocks, lines written, and time taken.

Example `report.md`:
```markdown
# Generation Report

## File Structure Status
```text
src/
├── main.py ✅
├── utils/
│   ├── helper.py ⚠️ placeholder
```

## Issues
⚠️ Placeholder created for utils/helper.py

## Unassigned Blocks
- 1 saved in `UNASSIGNED/unassigned_1.txt`

## Completed Summary
- Files in tree: 2
- Files created: 1
- Dirs created: 2
- Unassigned blocks: 1
- Issues: 1
- Time taken: 0.03s
- Lines written (approx): 10
- Placeholder-only files: 1
```

---

## ⚙️ CLI Options

| Option                  | Description                                                                 | Default                     | Example Usage                             |
|-------------------------|-----------------------------------------------------------------------------|-----------------------------|-------------------------------------------|
| `input`                 | Markdown file or folder path for `--folder-to-md`                            | Required                    | `project.md` or `my_folder`               |
| `-o, --output`          | Output folder (Markdown-to-folder) or Markdown file (folder-to-Markdown)     | `output_folder` or `folder_name.md` | `-o my_project` or `-o output.md`         |
| `--strict`              | Abort on warnings/errors                                                    | False                       | `--strict`                                |
| `--dry`                 | Dry run (no writing)                                                        | False                       | `--dry`                                   |
| `--preview`             | Preview planned tree and assignments (no writing)                            | False                       | `--preview`                               |
| `--verbose`             | Verbose logging                                                             | False                       | `--verbose`                               |
| `-q, --quiet`           | Suppress non-error output                                                   | False                       | `-q`                                      |
| `--debug`               | Debug logging                                                               | False                       | `--debug`                                 |
| `--skip-empty`          | Skip placeholder-only files                                                 | False                       | `--skip-empty`                            |
| `--no-overwrite`        | Do not overwrite existing files                                             | False                       | `--no-overwrite`                          |
| `--json-summary FILE`   | Write JSON summary to FILE                                                  | None                        | `--json-summary summary.json`             |
| `--ignore PATTERN`      | Glob patterns to ignore                                                     | []                          | `--ignore *.test.*`                       |
| `--files-always NAME`   | Force names as files                                                        | []                          | `--files-always README`                   |
| `--dirs-always NAME`    | Force names as directories                                                  | []                          | `--dirs-always src`                       |
| `--placeholders FILE`   | JSON file with placeholder overrides                                        | None                        | `--placeholders placeholders.json`        |
| `--config FILE`         | Path to `generator.config.json` for defaults                                 | None                        | `--config config.json`                    |
| `--strip-hints`         | Remove first-line rescue hints (e.g., `// file/path`)                       | False                       | `--strip-hints`                           |
| `--zip`                 | Zip the output folder                                                       | False                       | `--zip`                                   |
| `--tar`                 | Create tar.gz of the output folder                                          | False                       | `--tar`                                   |
| `--interactive`         | Prompt user for conflict resolution                                         | False                       | `--interactive`                           |
| `--html-report [FILE]`  | Write HTML interactive report (default: `report.html`)                       | None                        | `--html-report` or `--html-report out.html` |
| `--incremental`         | Regenerate only changed files using cache                                   | False                       | `--incremental`                           |
| `--set-exec`            | Set executable flag on `*.sh`, `Procfile`, `Makefile`                       | False                       | `--set-exec`                              |
| `--export-md FILE`      | Export generated project back to Markdown                                    | None                        | `--export-md export.md`                   |
| `--extension-report FILE`| Custom report file path                                                     | `report.md`                 | `--extension-report custom_report.md`     |
| `--folder-to-md`        | Convert folder to Markdown file                                             | False                       | `--folder-to-md`                          |
| `--no-compare`          | Disable file structure comparison for `--folder-to-md`                       | False                       | `--no-compare`                            |

---

## 📂 Usage Scenarios and Examples

### 1. Basic Markdown-to-Folder
**Goal**: Generate a project from a Markdown spec.
```bash
python generator.py project.md -o my_project
```
- **Input**: `project.md` with `## File Structure` and file contents.
- **Output**: `my_project/` with files, `report.md`, and optional `README.md`.
- **Warnings**:
  - Missing `File Structure` block → Exits with error.
  - Unassigned code blocks → Saved in `my_project/UNASSIGNED/`.
  - Ambiguous headings → Logged in `report.md`.

### 2. Folder-to-Markdown with .gitignore
**Goal**: Convert a folder to Markdown, excluding ignored files.
```bash
python generator.py --folder-to-md src output.md --json-summary summary.json
```
- **Input**: `src/` with `.gitignore` (e.g., `*.log`).
- **Output**: `output.md` with file structure and contents, `summary.json`.
- **Warnings**:
  - Unreadable files → Logged as warnings.
  - Invalid `.gitignore` patterns → Warning, includes all files.
  - Empty folder → Empty `File Structure` block.

### 3. Reproduce Folder from Generated Markdown
**Goal**: Ensure round-trip reproducibility.
```bash
python generator.py --folder-to-md test_folder test.md
python generator.py test.md -o test_folder_repro
```
- **Steps**:
  1. Generate `test.md` from `test_folder`.
  2. Reproduce `test_folder_repro` from `test.md`.
  3. Compare: `diff -r test_folder test_folder_repro`.
- **Warnings**:
  - Nested code blocks (e.g., in `report.md`) → Handled by backtick escaping.
  - Missing files in reproduction → Logged in `report.md`.

### 4. Dry Run with Preview
**Goal**: Preview file assignments without writing.
```bash
python generator.py project.md --preview --json-summary preview.json
```
- **Output**: Console preview of file assignments, `preview.json`.
- **Warnings**:
  - Ambiguous headings or fence info → Listed in preview.
  - Unassigned blocks → Reported in console and JSON.

### 5. Strict Mode with Error Handling
**Goal**: Abort on any issues.
```bash
python generator.py project.md -o strict_output --strict
```
- **Behavior**: Exits on warnings/errors (e.g., missing files, conflicts).
- **Warnings**:
  - Invalid paths → Immediate exit.
  - Unassigned blocks → Triggers exit.

### 6. Interactive Conflict Resolution
**Goal**: Resolve file conflicts manually.
```bash
python generator.py project.md -o output --interactive
```
- **Behavior**: Prompts user to resolve file/directory conflicts.
- **Warnings**:
  - Existing files (without `--no-overwrite`) → Prompts for action.
  - Directory vs. file conflicts → User input required.

### 7. Incremental Updates
**Goal**: Update only changed files.
```bash
python generator.py project.md -o output --incremental
```
- **Behavior**: Uses `.generator_cache.json` to skip unchanged files.
- **Warnings**:
  - Cache file missing/corrupted → Full regeneration.
  - File hash mismatches → Logged and updated.

### 8. Archive Output
**Goal**: Package the output folder.
```bash
python generator.py project.md -o output --zip --tar
```
- **Output**: `output.zip`, `output.tar.gz`.
- **Warnings**:
  - Disk space issues → Logged as errors.
  - Permissions errors → Logged in `report.md`.

### 9. Custom Reports and Summaries
**Goal**: Generate detailed reports.
```bash
python generator.py project.md -o output --json-summary summary.json --html-report report.html --extension-report custom_report.md
```
- **Output**: `summary.json`, `report.html`, `custom_report.md`.
- **Warnings**:
  - Write failures (e.g., permissions) → Logged in console.

### 10. Executable Permissions
**Goal**: Set executable flags for scripts.
```bash
python generator.py project.md -o output --set-exec
```
- **Behavior**: Sets executable permissions for `*.sh`, `Procfile`, `Makefile`.
- **Warnings**:
  - Permission errors → Logged in `report.md`.

---

## ⚠️ Common Warnings and Edge Cases

### Markdown-to-Folder
- **Missing `File Structure` Block**:
  - Error: Exits with code 3.
  - Fix: Ensure `## File Structure\n```text\n...\n``` exists.
- **Unassigned Code Blocks**:
  - Warning: Saved in `UNASSIGNED/unassigned_X.txt`.
  - Fix: Add `// file/path` hints or correct `## path` headings.
  - Example: `## unknown\n```python\ncode\n``` → Add `// src/main.py` in first line.
- **Ambiguous Headings**:
  - Warning: Logged if heading matches multiple files.
  - Fix: Use `--files-always` or unique paths.
- **Invalid Paths**:
  - Warning: Skipped if paths are malformed (e.g., `../file.py`).
  - Fix: Use valid relative paths in `File Structure`.
- **Directory vs. File Conflicts**:
  - Warning: Logged in `report.md`, prompts if `--interactive`.
  - Fix: Use `--dirs-always` or `--files-always`.

### Folder-to-Markdown
- **Unreadable Files**:
  - Warning: Skipped and logged (e.g., permission denied).
  - Fix: Ensure file read permissions.
- **Invalid `.gitignore` Patterns**:
  - Warning: Ignores faulty patterns, includes all files.
  - Fix: Validate `.gitignore` syntax.
- **Nested Code Blocks**:
  - Issue: Nested ``` in files (e.g., `report.md`) may confuse parser.
  - Fix: Backticks escaped (``` → \```) in output; unescaped during reproduction.
- **Empty Folder**:
  - Warning: Generates empty `File Structure` block.
  - Fix: None needed; expected behavior.
- **Comparison Failures** (without `--no-compare`):
  - Warning: Empty files or mismatches logged.
  - Fix: Check file contents or use `--no-compare`.

### Reproducibility Issues
- **Unassigned Blocks on Reproduction**:
  - Issue: Nested code blocks (e.g., in `report.md`) misparsed.
  - Fix: Ensured by backtick escaping/unescaping in `folder_to_markdown` and `map_headings_to_files`.
- **Missing Files**:
  - Warning: Logged if `File Structure` entries lack content.
  - Fix: Ensure all files in `File Structure` have corresponding `## path` sections.

---

## 📝 Example: Full Workflow

### Folder Setup
```
test_folder/
├── .gitignore      # *.txt
├── main.py         # print("Hello")
├── docs/
│   ├── readme.md   # # Docs\n```text
├── ignore.txt      # ignored
```

### Convert to Markdown
```bash
python generator.py --folder-to-md test_folder test.md --json-summary summary.json
```
**Output (`test.md`)**:
```markdown
# Generated Folder Structure
## File Structure
```text
docs/readme.md
main.py
```

## main.py
```python
print("Hello")
```

## docs/readme.md
```md
# Docs
\```text
info
\```
```

**Output (`summary.json`)**:
```json
{
  "files_converted": 2,
  "warnings": []
}
```

### Reproduce Folder
```bash
python generator.py test.md -o test_folder_repro --skip-empty
```
**Output**:
- `test_folder_repro/docs/readme.md`: Matches original content.
- `test_folder_repro/main.py`: Matches original content.
- `test_folder_repro/report.md`: Contains generation report.
- No `UNASSIGNED/` directory.
- Verify: `diff -r test_folder test_folder_repro` (ignores `.gitignore`, `ignore.txt`).

### Handle Warnings
If `test.md` has an unassigned block:
```markdown
## unknown
```python
code
```
```
- **Warning**: `unassigned_1.txt` in `UNASSIGNED/`.
- **Fix**: Add `// main.py` to the code block or rename heading to `## main.py`.

---

## 🛠️ Troubleshooting

- **Error: "Input file not found"**:
  - Cause: Invalid `input` path.
  - Fix: Verify path exists (e.g., `ls project.md`).
- **Error: "Could not find a 'File Structure' block"**:
  - Cause: Missing `## File Structure\n```text\n...`.
  - Fix: Add the block to the Markdown file.
- **Warning: Unassigned blocks**:
  - Cause: Code blocks without matching `## path` or hints.
  - Fix: Use `--strip-hints` with proper hints or correct headings.
- **Warning: File/directory conflict**:
  - Cause: Same name used as file and directory.
  - Fix: Use `--interactive`, `--files-always`, or `--dirs-always`.
- **Reproducibility Failure**:
  - Cause: Nested code blocks misparsed.
  - Fix: Ensure backtick escaping (`folder_to_markdown`) and unescaping (`map_headings_to_files`) are applied.
- **Permission Errors**:
  - Cause: Cannot read/write files.
  - Fix: Check permissions or run with elevated privileges.

---

## 📖 License

MIT – Free to use, modify, and distribute.

---

## 📝 Changelog (latest)

- Added `--folder-to-md` to convert folders to reproducible Markdown.
- Added `--no-compare` to skip structure comparison in folder-to-Markdown mode.
- Enhanced backtick escaping for nested code blocks to ensure reproducibility.
- Added `--strip-hints` to remove rescue hints.
- Added `--zip` and `--tar` for archiving output.
- Default output folder: `output_folder`; default Markdown: `folder_name.md`.

---