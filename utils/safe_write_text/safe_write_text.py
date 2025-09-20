from pathlib import Path
from typing import List

def safe_write_text(path: Path, content: str, warnings: List[str], no_overwrite: bool = False) -> bool:
    """
    Write text safely creating parent directories.
    Returns True if file was written, False if skipped or failed.
    Appends warnings on issues.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.is_dir():
                warnings.append(f"⚠️ Conflict: Tried to write file but a directory exists at {path}")
                return False
            if no_overwrite:
                warnings.append(f"ℹ️ Skipped existing file {path} due to --no-overwrite")
                return False
        if path.parent.exists() and path.parent.is_file():
            warnings.append(f"⚠️ Invalid structure: Parent is a file for {path}")
            return False
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        warnings.append(f"⚠️ Failed to write {path}: {e}")
        return False