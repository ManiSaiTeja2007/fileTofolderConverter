from pathlib import Path
from typing import List

def export_to_markdown(folder: Path, md_path: Path):
    lines = ["# Exported Project", "## File Structure", "```text"]
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if p.is_dir():
            lines.append(str(rel) + "/")
        else:
            lines.append(str(rel))
    lines.append("```")
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if p.is_file():
            lines.append(f"\n## {rel}")
            ext = p.suffix.lstrip(".")
            lang = "text" if not ext else ext
            content = p.read_text(encoding="utf-8")
            lines.append(f"```{lang}\n{content}\n```")
    md_path.write_text("\n".join(lines), encoding="utf-8")