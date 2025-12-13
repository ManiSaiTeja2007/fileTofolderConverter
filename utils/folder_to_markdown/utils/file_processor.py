"""File processing utilities."""
from pathlib import Path
from typing import List, Tuple, Set, Optional, Pattern
import logging

# Import from project utils
from utils.is_probably_file.is_probably_file import is_probably_file

from .pattern_matcher import should_ignore_path, get_default_ignore_patterns
from ...constants import LANGUAGE_EXTENSIONS, BINARY_EXTENSIONS

def detect_language(file_path: Path) -> str:
    """
    Detect programming language based on file extension and name.
    """
    name_lower = file_path.name.lower()
    
    # Special case files
    if name_lower in {'dockerfile', 'makefile', '.gitignore'}:
        return name_lower.replace('.', '')

    ext = file_path.suffix.lstrip('.').lower()
    return LANGUAGE_EXTENSIONS.get(ext, "text")

def read_file_safely(file_path: Path, max_size: int = 1024 * 1024) -> Optional[str]:
    """
    Safely read text file with size limits and encoding handling.
    Skip binary files based on extension.
    """
    # Skip known binary extensions
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return "# Binary file (skipped)"
    
    try:
        # Check file size
        if file_path.stat().st_size > max_size:
            return f"# File too large ({file_path.stat().st_size} bytes), skipped"
            
        content = file_path.read_text(encoding="utf-8", errors="replace").rstrip()
        # Escape backticks to prevent Markdown parser issues
        content = content.replace("```", r"\`\`\`")
        return content
        
    except UnicodeDecodeError:
        return "# Binary or non-text file, skipped"
    except Exception as e:
        return f"# Error reading file: {str(e)}"

def collect_files(
    folder: Path,
    ignore_patterns: Set[Pattern],
    unignore_patterns: Set[Pattern],
    files_always: Set[str],
    dirs_always: Set[str],
    max_file_size: int = 1024 * 1024
) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """
    Collect files to include in markdown with proper filtering.
    """
    files_to_write = []
    warnings = []
    default_ignore_patterns = get_default_ignore_patterns()
    
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
            
        rel_path = path.relative_to(folder).as_posix()
        
        # Skip ignored paths
        if should_ignore_path(rel_path, ignore_patterns, unignore_patterns, default_ignore_patterns):
            continue
        
        # Skip directories that are treated as files
        if path.is_dir() and is_probably_file(path.name, files_always, dirs_always):
            continue
            
        # Read file content
        content = read_file_safely(path, max_file_size)
        if content is None:
            warnings.append(f"⚠️ Skipped {rel_path}: Read error")
            continue
            
        lang = detect_language(path)
        files_to_write.append((rel_path, lang, content))
    
    return files_to_write, warnings