"""ASCII tree building utilities."""
from pathlib import Path
from typing import List, Set, Pattern
import logging

# Import from project utils (assuming these exist in your project)
from utils.is_probably_file.is_probably_file import is_probably_file

from .pattern_matcher import should_ignore_path, get_default_ignore_patterns
from ...constants import EXPLICIT_IGNORE_DIRS  # NEW: Import explicit ignore dirs

def build_ascii_tree(
    root: Path,
    ignore_patterns: Set[Pattern],
    unignore_patterns: Set[Pattern],
    files_always: Set[str],
    dirs_always: Set[str],
    max_depth: int = 20
) -> List[str]:
    """
    Generate ASCII tree representation of directory structure, excluding ignored paths.
    """
    default_ignore_patterns = get_default_ignore_patterns()
    
    def _walk_dir(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
        if depth > max_depth:
            return []
            
        lines = []
        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError as e:
            return []
        except Exception as e:
            return []

        # Filter out ignored entries first
        valid_entries = []
        for entry in entries:
            rel_path = str(entry.relative_to(root)).replace("\\", "/")
            
            # PERMANENT FIX: Explicitly ignore directories in EXPLICIT_IGNORE_DIRS
            if entry.is_dir() and entry.name.lower() in [d.lower() for d in EXPLICIT_IGNORE_DIRS]:
                continue
                
            if not should_ignore_path(rel_path, ignore_patterns, unignore_patterns, default_ignore_patterns):
                valid_entries.append(entry)

        # If no valid entries after filtering, don't show this directory at all
        if not valid_entries:
            return []

        for i, entry in enumerate(valid_entries):
            is_last = i == len(valid_entries) - 1
            name = entry.name
            rel_path = str(entry.relative_to(root)).replace("\\", "/")

            # Determine if entry is a file or directory
            is_file = is_probably_file(name, files_always, dirs_always)
            connector = "└── " if is_last else "├── "
            entry_suffix = '/' if entry.is_dir() and not is_file else ''
            lines.append(f"{prefix}{connector}{name}{entry_suffix}")

            # Recurse into directories
            if entry.is_dir() and not is_file:
                new_prefix = prefix + ("    " if is_last else "│   ")
                child_lines = _walk_dir(entry, new_prefix, depth + 1)
                # Only add this directory if it has visible children
                if child_lines:
                    lines.extend(child_lines)
        
        return lines

    try:
        tree_lines = _walk_dir(root)
        return tree_lines if tree_lines else ["# Empty directory"]
    except Exception as e:
        return ["# Error building directory tree"]