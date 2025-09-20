from pathlib import Path
import re

def validate_entry_path(entry: str) -> str | None:
    """
    Return None if entry looks safe.
    Otherwise return an error string describing the problem.
    Rules:
    - No absolute paths (must not start with '/')
    - No parent traversal that escapes root ('..' as a segment)
    - No Windows drive-letter like 'C:\'
    """
    if not entry:
        return "Empty path"
    if entry.startswith("/") or entry.startswith("\\"):
        return "Absolute paths are not allowed"
    if ".." in Path(entry).parts:
        return "Parent traversal ('..') not allowed"
    if re.match(r"^[A-Za-z]:\\", entry):
        return "Absolute Windows paths not allowed"
    return None