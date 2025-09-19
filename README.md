# Markdown → Project Generator

`generator.py` is a Python utility to convert a **Markdown specification** into a fully scaffolded **project folder**.

---

## ✨ Features

* **Markdown-driven scaffolding**
  Parse `## File Structure` ASCII tree → directories & files.
* **Code mapping**
  VS Code–style headings → fenced code blocks → file contents.
* **Rescue mechanism**
  Re-attach unassigned code using `// file/path` or `# file/path` hints.
* **Validation**
  Preflight checks, conflict detection, strict enforcement.
* **Configurable**

  * Skip empty files (`--skip-empty`)
  * Ignore patterns (`--ignore *.test.*`)
  * Force treat names as files/dirs (`--files-always`, `--dirs-always`)
  * Strip rescue hints (`--strip-hints`)
  * Zip final output (`--zip`)
* **Reports**

  * `report.md` → audit log with ✅/⚠️/❌ status
  * Optional JSON summary (`--json-summary`)
  * Notes on rescued blocks and ambiguous hints
* **Documentation support**
  Intro/system notes from Markdown → generated project `README.md`.

---

## 🚀 Quickstart

1. Create a spec (`folder.md`)

2. Run generator:

```bash
python generator.py folder.md -o output_folder --skip-empty
```

3. Check results:

   * Files scaffolded in `output_folder/`
   * `report.md` inside `output_folder/`
   * `README.md` populated with intro/arch text
   * Optionally `output_folder.zip` if `--zip` is used

---

## 📊 Reports

Each run generates a **report**:

* File tree with ✅ (ok), ⚠️ (placeholder), ❌ (missing)
* Warnings & errors
* Notes on rescued mappings (`// hint/path`)
* Count of files/dirs/unassigned
* Time taken

Example snippet from `report.md`:

```text
backend/main.py ✅
backend/utils.py ⚠️ placeholder
frontend/pages/index.tsx ✅
```

---

## ⚙️ CLI Options

| Option                  | Description                               |
| ----------------------- | ----------------------------------------- |
| `-o FOLDER`             | Output folder (default: `output_folder`)  |
| `--skip-empty`          | Skip placeholder-only files               |
| `--ignore PATTERN`      | Glob patterns to ignore                   |
| `--files-always`        | Force names always as files               |
| `--dirs-always`         | Force names always as dirs                |
| `--json-summary`        | Write JSON summary                        |
| `--extension-report`    | Custom report file (default: `report.md`) |
| `--strip-hints`         | Remove first-line rescue hints in files   |
| `--zip`                 | Zip the generated output folder           |
| `--strict`              | Abort on warnings/errors                  |
| `--dry`                 | Dry run (no writing)                      |
| `--verbose` / `--debug` | Verbose logging                           |
| `-q, --quiet`           | Suppress non-error output                 |

---

## 📂 Example: Demo Run

```bash
python generator.py folder.md -o demo-output --skip-empty --zip --json-summary summary.json
```

Produces:

* `demo-output/` project structure
* `report.md` with audit log
* `summary.json` (machine-readable)
* `README.md` with intro/system notes
* `demo-output.zip`

---

## 📝 Changelog (latest)

* Default output folder → `output_folder`
* Added `--strip-hints` to remove rescue hints before writing
* Added `--zip` to package generated project into a `.zip`

---

## 📖 License

MIT – Free to use and modify.
