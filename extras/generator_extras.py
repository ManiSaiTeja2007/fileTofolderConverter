"""
generator_extras.py
Phase 2 – Usability & Developer Experience features
Used only when advanced flags are requested.
"""

import os
import sys
import stat
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict

# -------------------------
# Interactive conflict resolution
# -------------------------
def resolve_conflict_interactive(hint: str, candidates: List[str]) -> str:
    print(f"\n⚠️ Ambiguous hint '{hint}' matches multiple files:")
    for idx, c in enumerate(candidates, 1):
        print(f"  {idx}. {c}")
    choice = input("Choose target (number or Enter to skip): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return None

# -------------------------
# HTML Report Generator
# -------------------------
def write_html_report(tree_entries: List[str], out_root: Path, summary: Dict, html_path: Path):
    html_lines = [
        "<html><head><style>",
        "body { font-family: monospace; }",
        ".ok { color: green; } .warn { color: orange; } .err { color: red; }",
        "</style></head><body>",
        "<h1>Generation Report</h1>",
        "<ul>"
    ]
    for entry in tree_entries:
        path = out_root / entry
        if path.is_dir():
            html_lines.append(f"<li><b>{entry}/</b></li>")
        else:
            if not path.exists():
                html_lines.append(f"<li class='err'>{entry} ❌ MISSING</li>")
            else:
                text = path.read_text(encoding="utf-8").strip()
                if not text or text.startswith(("# TODO", "// TODO", "<!-- TODO")):
                    html_lines.append(f"<li class='warn'>{entry} ⚠️ placeholder</li>")
                else:
                    html_lines.append(f"<li class='ok'>{entry} ✅</li>")
    html_lines.append("</ul><hr>")
    html_lines.append("<h2>Summary</h2><pre>" + json.dumps(summary, indent=2) + "</pre>")
    html_lines.append("</body></html>")
    html_path.write_text("\n".join(html_lines), encoding="utf-8")

# -------------------------
# Incremental Generation Support
# -------------------------
def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def should_update(path: Path, content: str, cache: Dict) -> bool:
    new_hash = compute_hash(content)
    old_hash = cache.get(str(path))
    return new_hash != old_hash

def save_cache(cache_file: Path, cache: Dict):
    cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")

def load_cache(cache_file: Path) -> Dict:
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return {}

# -------------------------
# Executable flags
# -------------------------
def set_executable(path: Path):
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IEXEC)
    except Exception as e:
        logging.warning(f"⚠️ Failed to set executable on {path}: {e}")

# -------------------------
# Export folder back to Markdown
# -------------------------
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
