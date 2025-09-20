from typing import List
from pathlib import Path

def infer_targets_from_fence_info(info: str, tree_entries: List[str]) -> List[str]:
    if not info:
        return []
    info_clean = info.strip().lower()
    candidates = []
    for f in tree_entries:
        base = Path(f).name.lower()
        if base == info_clean:
            candidates.append(f)
            continue
        if info_clean in base:
            candidates.append(f)
            continue
        if info_clean in f.lower():
            candidates.append(f)
    return candidates