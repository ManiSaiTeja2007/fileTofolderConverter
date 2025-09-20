from typing import List
from pathlib import Path
from markdown_it.token import Token

from utils.is_probably_file.is_probably_file import is_probably_file

def extract_project_readme(tokens: List[Token], tree_entries: List[str]) -> str:
    file_names = {Path(f).name for f in tree_entries if is_probably_file(Path(f).name)}
    out_sections: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.type == "heading_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            if Path(heading_text).name in file_names or heading_text.strip().lower() == "file structure":
                i += 1
                continue
            section_lines: List[str] = [f"# {heading_text}" if not heading_text.startswith("#") else heading_text]
            i += 1
            while i < n and tokens[i].type != "heading_open":
                t = tokens[i]
                if t.type == "inline":
                    section_lines.append(t.content)
                elif t.type == "fence":
                    info = getattr(t, "info", "") or ""
                    fence_block = "```" + info + "\n" + t.content.rstrip() + "\n```"
                    section_lines.append(fence_block)
                elif t.type == "paragraph_open":
                    inlinep = tokens[i + 1] if (i + 1) < n else None
                    if inlinep and inlinep.type == "inline":
                        section_lines.append(inlinep.content)
                    j = i + 1
                    while j < n and tokens[j].type != "paragraph_close":
                        j += 1
                    i = j
                i += 1
            out_sections.append("\n\n".join(section_lines).strip())
            continue
        i += 1
    return "\n\n".join(out_sections).strip()