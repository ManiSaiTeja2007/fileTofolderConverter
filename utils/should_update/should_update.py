from pathlib import Path
from typing import Dict

from utils.compute_hash.compute_hash import compute_hash

def should_update(path: Path, content: str, cache: Dict) -> bool:
    new_hash = compute_hash(content)
    old_hash = cache.get(str(path))
    return new_hash != old_hash