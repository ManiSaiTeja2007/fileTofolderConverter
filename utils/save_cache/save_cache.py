import json
from pathlib import Path

def save_cache(cache_file: Path, cache: dict) -> None:
    cache_file.write_text(json.dumps(cache), encoding="utf-8")