"""Pattern matching utilities for ignore patterns."""
from pathlib import Path
from typing import Set, Tuple, Pattern
import re
import fnmatch
import logging
from functools import lru_cache

from ...constants import DEFAULT_IGNORE_PATTERNS, EXPLICIT_IGNORE_DIRS  

@lru_cache(maxsize=1024)

def load_gitignore_patterns(gitignore_path: Path) -> Tuple[Set[Pattern], Set[Pattern]]:
    """
    Load .gitignore patterns, separating ignores and un-ignores (!patterns).
    Returns compiled regex patterns for efficient matching.
    """
    ignores: Set[Pattern] = set()
    unignores: Set[Pattern] = set()
    
    if not gitignore_path.exists():
        return ignores, unignores
        
    try:
        with gitignore_path.open("r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                    
                if line.startswith("!"):
                    pattern = pattern_to_regex(line[1:])
                    if pattern.pattern != r'(?!x)x':  # Skip invalid patterns
                        unignores.add(pattern)
                else:
                    pattern = pattern_to_regex(line)
                    if pattern.pattern != r'(?!x)x':  # Skip invalid patterns
                        ignores.add(pattern)
                        
    except Exception as e:
        logging.warning(f"⚠️ Failed to parse .gitignore at {gitignore_path}: {e}")
        
    return ignores, unignores

def get_default_ignore_patterns() -> Set[Pattern]:
    """Get pre-compiled default ignore patterns."""
    return {pattern_to_regex(pat) for pat in DEFAULT_IGNORE_PATTERNS}

def pattern_to_regex(pattern: str) -> Pattern:
    """
    Convert .gitignore or glob pattern to compiled regex pattern.
    Cached for performance with common patterns.
    """
    pattern = pattern.strip()
    if not pattern or pattern.startswith("#"):
        return re.compile(r'(?!x)x')  # Never matches
    
    # Handle directory patterns
    is_dir_pattern = pattern.endswith('/')
    if is_dir_pattern:
        pattern = pattern[:-1]
    
    # Convert to regex using fnmatch
    regex_pattern = fnmatch.translate(pattern)
    
    # Handle directory matching - directory and all its contents
    if is_dir_pattern or '/' in pattern:
        regex_pattern = regex_pattern.replace(r'\Z', r'(/.*)?\Z')
    
    try:
        return re.compile(regex_pattern)
    except re.error:
        logging.warning(f"Invalid regex pattern: {regex_pattern} from original: {pattern}")
        return re.compile(r'(?!x)x')  # Never matches on error

def should_ignore_path(
    rel_path: str,
    ignore_patterns: Set[Pattern],
    unignore_patterns: Set[Pattern],
    default_ignore_patterns: Set[Pattern]
) -> bool:
    """
    Determine if a path should be ignored based on patterns.
    Unignore patterns take precedence over ignore patterns.
    """
    # Check if explicitly un-ignored
    if any(pattern.match(rel_path) for pattern in unignore_patterns):
        return False
    
    # NEW: Check explicit directory names (case-insensitive)
    path_obj = Path(rel_path)
    for part in path_obj.parts:
        if part.lower() in [d.lower() for d in EXPLICIT_IGNORE_DIRS]:
            return True
    
    # Check if ignored by default or custom patterns
    all_ignore_patterns = default_ignore_patterns | ignore_patterns
    if any(pattern.match(rel_path) for pattern in all_ignore_patterns):
        return True
    
    return False