from pathlib import Path
from typing import Optional, Set

from utils.config.config import SPECIAL_FILES

def is_probably_file(name: str, files_always: Optional[Set] = None, dirs_always: Optional[Set] = None) -> bool:
    """Heuristic to decide whether a segment is a file."""
    if not name:
        return False
    files_always = set(x.lower() for x in (files_always or set()))
    dirs_always = set(x.lower() for x in (dirs_always or set()))
    if name.endswith("/"):
        return False
    base = Path(name).name
    base_lower = base.lower()
    if base_lower in dirs_always:
        return False
    if base_lower in files_always or base_lower in SPECIAL_FILES:
        return True
    if base_lower == "dockerfile":
        return True
    return "." in base