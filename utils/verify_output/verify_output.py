from pathlib import Path
from typing import List, Dict
from utils.is_probably_file.is_probably_file import is_probably_file

def verify_output(out_root: Path, tree_files: List[str], code_map: Dict[str, List[str]], warnings: List[str]):
    for f in tree_files:
        name = Path(f).name
        if not is_probably_file(name):
            continue
        path = out_root / f
        if not path.exists():
            warnings.append(f"❌ Missing file: {f}")
        else:
            try:
                size = path.stat().st_size
            except Exception:
                size = 0
            if size == 0:
                warnings.append(f"⚠️ Empty file: {f}")
            if len(code_map.get(f, [])) > 1:
                warnings.append(f"⚠️ File {f} had multiple code blocks merged")