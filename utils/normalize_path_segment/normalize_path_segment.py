def normalize_path_segment(seg: str) -> str:
    return seg.strip().rstrip("/").strip()