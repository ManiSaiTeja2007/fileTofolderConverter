from pathlib import Path
import stat
import logging

def set_executable(path: Path):
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IEXEC)
    except Exception as e:
        logging.warning(f"⚠️ Failed to set executable on {path}: {e}")