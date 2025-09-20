from typing import List, Tuple
import re
from pathlib import Path

from utils.is_probably_file.is_probably_file import is_probably_file

def parse_ascii_tree_block(block_text: str, files_always: set, dirs_always: set) -> List[str]:
    lines = block_text.splitlines()
    entries: List[str] = []
    stack: List[Tuple[str, int]] = [("", 0)]

    for raw in lines:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" │"))
        line = re.sub(r"^[\s│├└─]+", "", raw).rstrip("/")
        if not line:
            continue
        if line.strip().startswith("#"):
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        if " //" in line:
            line = line.split(" //", 1)[0].strip()
        if " -- " in line:
            line = line.split(" --", 1)[0].strip()
        if not line:
            continue
        while stack and indent <= stack[-1][1]:
            stack.pop()
        parent = stack[-1][0] if stack else ""
        full = f"{parent}/{line}" if parent else line
        entries.append(full)
        if not is_probably_file(line, files_always, dirs_always):
            stack.append((full, indent))
    if entries:
        root = entries[0]
        if not is_probably_file(Path(root).name, files_always, dirs_always):
            normalized: List[str] = []
            for e in entries[1:]:
                if e.startswith(root + "/"):
                    normalized.append(e)
                else:
                    normalized.append(f"{root}/{e}")
            return [root] + normalized
    return entries