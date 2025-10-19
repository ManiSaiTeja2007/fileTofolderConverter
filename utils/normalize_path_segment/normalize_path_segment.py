from pathlib import Path
import re
import logging
from typing import Union

def normalize_path_segment(seg: Union[str, Path]) -> str:
    """
    Normalize a path segment by stripping whitespace and trailing slashes.
    Handles various edge cases and provides robust normalization.
    
    Args:
        seg: Path segment to normalize (string or Path object)
        
    Returns:
        Normalized path segment as string
        
    Examples:
        >>> normalize_path_segment("  src/  ")
        'src'
        >>> normalize_path_segment("utils//")
        'utils'
        >>> normalize_path_segment("  ")
        ''
        >>> normalize_path_segment(Path("docs/"))
        'docs'
    """
    # Handle None input
    if seg is None:
        return ""
    
    # Convert Path objects to string
    if isinstance(seg, Path):
        seg = str(seg)
    
    # Ensure it's a string
    if not isinstance(seg, str):
        try:
            seg = str(seg)
        except Exception as e:
            logging.debug(f"⚠️ Failed to convert path segment to string: {e}")
            return ""
    
    # Strip whitespace and normalize
    normalized = seg.strip()
    
    # Remove trailing slashes (both forward and backward)
    normalized = re.sub(r'[/\\]+$', '', normalized)
    
    # Remove leading ./ or .\
    normalized = re.sub(r'^\.[/\\]', '', normalized)
    
    # Collapse multiple slashes into single forward slash
    normalized = re.sub(r'[/\\]+', '/', normalized)
    
    return normalized.strip()

def normalize_path_segments(segments: list) -> list:
    """
    Normalize multiple path segments.
    
    Args:
        segments: List of path segments to normalize
        
    Returns:
        List of normalized path segments
    """
    if not segments:
        return []
    
    normalized_segments = []
    for seg in segments:
        normalized = normalize_path_segment(seg)
        if normalized:  # Only include non-empty segments
            normalized_segments.append(normalized)
    
    return normalized_segments

def build_normalized_path(*segments) -> str:
    """
    Build a normalized path from multiple segments.
    
    Args:
        *segments: Path segments to join and normalize
        
    Returns:
        Normalized path string
    """
    normalized_segments = normalize_path_segments(list(segments))
    return "/".join(normalized_segments)

# Test function for the normalization
def test_normalize_path_segment():
    """Test function to verify normalization behavior."""
    test_cases = [
        ("  src/  ", "src"),
        ("utils//", "utils"),
        ("  ", ""),
        (Path("docs/"), "docs"),
        ("./src", "src"),
        ("src\\", "src"),
        ("src//subdir", "src/subdir"),
        ("src\\\\subdir", "src/subdir"),
        (None, ""),
        ("", ""),
        ("src/subdir/", "src/subdir"),
        ("  src/subdir  ", "src/subdir"),
    ]
    
    print("Testing normalize_path_segment:")
    for input_val, expected in test_cases:
        result = normalize_path_segment(input_val)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{input_val}' -> '{result}' (expected: '{expected}')")
    
    # Test multiple segments
    print("\nTesting normalize_path_segments:")
    segments = ["  src/  ", "  utils  ", "file.py  "]
    result = normalize_path_segments(segments)
    print(f"  {segments} -> {result}")
    
    # Test path building
    print("\nTesting build_normalized_path:")
    path = build_normalized_path("  src/  ", "  utils  ", "file.py  ")
    print(f"  Built path: {path}")

if __name__ == "__main__":
    test_normalize_path_segment()