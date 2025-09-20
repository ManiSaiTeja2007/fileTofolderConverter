from pathlib import Path
from typing import List, Dict

from utils.is_probably_file.is_probably_file import is_probably_file

def write_extension_report(
    out_root: Path,
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    unassigned: List[str],
    warnings: List[str],
    errors: List[str],
    report_path: Path,
    summary: dict,
    elapsed: float,
    rescued_warnings: List[str],
):
    lines: List[str] = []
    lines.append("# Generation Report")
    lines.append("")
    lines.append("## File Structure Status")
    lines.append("")
    lines.append("```text")
    for entry in tree_entries:
        parts = entry.split("/")
        depth = len(parts) - 1
        prefix = ("│   " * (depth - 1)) + ("├── " if depth > 0 else "")
        name = parts[-1]
        path = out_root / entry
        if path.exists() and path.is_dir():
            lines.append(f"{prefix}{name}/")
        else:
            if not path.exists():
                lines.append(f"{prefix}{name} ❌ MISSING")
            else:
                try:
                    content = path.read_text(encoding="utf-8").strip()
                except Exception:
                    content = ""
                if not content or content.startswith(("# TODO", "// TODO", "<!-- TODO")):
                    lines.append(f"{prefix}{name} ⚠️ placeholder")
                else:
                    lines.append(f"{prefix}{name} ✅")
    lines.append("```")
    if errors or warnings or rescued_warnings:
        lines.append("\n## Issues")
        if errors:
            lines.append("### Errors")
            for e in errors:
                lines.append(f"- ❌ {e}")
        if warnings:
            lines.append("### Warnings")
            for w in warnings:
                lines.append(f"- ⚠️ {w}")
        if rescued_warnings:
            lines.append("### Rescued / Mapping Notes")
            for r in rescued_warnings:
                lines.append(f"- ℹ️ {r}")
    else:
        lines.append("\n## Issues\n✅ None")
    if unassigned:
        lines.append("\n## Unassigned Blocks")
        lines.append(f"- {len(unassigned)} saved in `UNASSIGNED/`")
    else:
        lines.append("\n## Unassigned Blocks\n✅ None")
    lines.append("\n## Completed Summary")
    lines.append(f"- Files in tree: {summary.get('files_in_tree', 0)}")
    lines.append(f"- Files created: {summary.get('files_created', 0)}")
    lines.append(f"- Dirs created: {summary.get('dirs_created', 0)}")
    lines.append(f"- Unassigned blocks: {summary.get('unassigned_blocks', 0)}")
    lines.append(f"- Issues: {len(warnings) + len(errors)}")
    lines.append(f"- Time taken: {elapsed:.2f}s")
    lines.append(f"- Lines written (approx): {summary.get('lines_written', 0)}")
    lines.append(f"- Placeholder-only files: {summary.get('placeholders_created', 0)}")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")