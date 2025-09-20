from pathlib import Path
from typing import List, Dict
import json

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