from typing import List, Tuple, Set, Optional
import re
import logging
from pathlib import Path

from utils.is_probably_file.is_probably_file import is_probably_file
from utils.normalize_path_segment.normalize_path_segment import normalize_path_segment

# Pre-compile regex patterns for performance
INDENT_PATTERN = re.compile(r"^[\s│├└─]+")
COMMENT_PATTERN = re.compile(r"\s*(#|//|--)\s+.*$")
TRAILING_SLASH_PATTERN = re.compile(r"/+$")

def clean_tree_line(raw_line: str) -> Optional[str]:
    """
    Clean and normalize a single line from ASCII tree.
    """
    if not raw_line or not raw_line.strip():
        return None
    
    line = raw_line.rstrip()  # Only strip trailing whitespace
    
    # Skip comment lines
    if line.strip().startswith('#'):
        return None
    
    # Replace tree characters with spaces but maintain structure
    cleaned = line
    for char in ['│', '├', '└']:
        cleaned = cleaned.replace(char, ' ')
    
    cleaned = cleaned.replace('──', '  ')
    cleaned = cleaned.replace('─', ' ')
    
    content = cleaned.strip()
    
    if not content:
        return None
    
    # Remove trailing slash but note it
    has_trailing_slash = content.endswith('/')
    if has_trailing_slash:
        content = content.rstrip('/')
    
    # Remove inline comments
    if ' #' in content:
        content = content.split(' #', 1)[0].strip()
    if ' //' in content:
        content = content.split(' //', 1)[0].strip()
    if ' -- ' in content:
        content = content.split(' -- ', 1)[0].strip()
    
    content = content.strip()
    if not content:
        return None
    
    # Add back trailing slash for directory detection
    if has_trailing_slash:
        content += '/'
    
    return content

def calculate_indent_level(line: str) -> int:
    """
    Calculate indent level based on ASCII tree characters.
    
    Args:
        line: Line from ASCII tree
        
    Returns:
        Indent level (number of spaces/characters)
    """
    # Count visual indent using tree characters
    indent_chars = 0
    for char in line:
        if char in ' │├└─':
            indent_chars += 1
        else:
            break
    return indent_chars

def build_directory_stack(
    current_indent: int, 
    stack: List[Tuple[str, int]]
) -> List[Tuple[str, int]]:
    """
    Maintain and update the directory stack based on current indent level.
    
    Args:
        current_indent: Current line's indent level
        stack: Current directory stack
        
    Returns:
        Updated directory stack
    """
    # Pop stack until we find parent with smaller indent
    while stack and current_indent <= stack[-1][1]:
        stack.pop()
    
    return stack

def should_treat_as_directory(
    line: str, 
    files_always: Set[str], 
    dirs_always: Set[str]
) -> bool:
    """
    Determine if a line should be treated as a directory.
    
    Args:
        line: Cleaned line content
        files_always: Set of names to always treat as files
        dirs_always: Set of names to always treat as directories
        
    Returns:
        True if should be treated as directory
    """
    return not is_probably_file(line, files_always, dirs_always)

def normalize_entries_relative_to_root(entries: List[str], files_always: Set[str], dirs_always: Set[str]) -> List[str]:
    """
    Normalize entries to be relative to the root directory.
    
    Args:
        entries: List of parsed entries
        files_always: Set of names to always treat as files
        dirs_always: Set of names to always treat as directories
        
    Returns:
        Normalized list of entries
    """
    if not entries:
        return []
    
    root = entries[0]
    
    # If root is a file, return entries as-is
    if is_probably_file(Path(root).name, files_always, dirs_always):
        return entries
    
    normalized = [root]
    
    for entry in entries[1:]:
        if entry.startswith(root + '/'):
            # Entry is already relative to root
            normalized.append(entry)
        else:
            # Make entry relative to root
            normalized.append(f"{root}/{entry}")
    
    return normalized

def parse_ascii_tree_block(
    block_text: str, 
    files_always: Optional[Set[str]] = None, 
    dirs_always: Optional[Set[str]] = None
) -> List[str]:
    """
    Parse ASCII tree block into a list of file and directory paths.
    """
    # Input validation
    if not block_text or not isinstance(block_text, str):
        logging.warning("⚠️ Empty or invalid ASCII tree block provided")
        return []
    
    files_always = files_always or set()
    dirs_always = dirs_always or set()
    
    try:
        lines = block_text.splitlines()
        entries: List[str] = []
        stack: List[Tuple[str, int]] = [("", 0)]  # (path, indent_level)
        
        for line_num, raw_line in enumerate(lines, 1):
            try:
                # Clean and validate line
                cleaned_line = clean_tree_line(raw_line)
                if not cleaned_line:
                    continue
                
                # Calculate indent level
                indent_level = calculate_indent_level(raw_line)
                
                # Update directory stack
                stack = build_directory_stack(indent_level, stack)
                
                # Get parent directory
                parent_path = stack[-1][0] if stack else ""
                
                # Build full path
                if parent_path:
                    full_path = f"{parent_path}/{cleaned_line}"
                else:
                    full_path = cleaned_line
                
                # Normalize path
                full_path = normalize_path_segment(full_path)
                
                entries.append(full_path)
                
                # Add to stack if it's a directory
                if should_treat_as_directory(cleaned_line, files_always, dirs_always):
                    stack.append((full_path, indent_level))
                    
            except Exception as e:
                logging.warning(f"⚠️ Error parsing line {line_num}: '{raw_line}' - {e}")
                continue
        
        # Normalize entries relative to root
        if entries:
            entries = normalize_entries_relative_to_root(entries, files_always, dirs_always)
        
        logging.info(f"✅ Parsed ASCII tree: {len(entries)} entries")
        return entries
        
    except Exception as e:
        logging.error(f"❌ Failed to parse ASCII tree block: {e}")
        return []

def validate_parsed_tree(entries: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate parsed tree entries for consistency.
    
    Args:
        entries: List of parsed entries
        
    Returns:
        Tuple of (is_valid, warnings)
    """
    warnings = []
    
    if not entries:
        warnings.append("No entries parsed from tree")
        return False, warnings
    
    # Check for duplicates
    seen = set()
    duplicates = []
    for entry in entries:
        if entry in seen:
            duplicates.append(entry)
        seen.add(entry)
    
    if duplicates:
        warnings.append(f"Found duplicate entries: {duplicates}")
    
    # Check for proper hierarchy
    entries_set = set(entries)
    for entry in entries:
        path = Path(entry)
        # Check if all parent directories exist in the tree
        for parent in path.parents:
            if parent != Path('.') and str(parent) not in entries_set:
                warnings.append(f"Missing parent directory in tree: {parent} for {entry}")
                break
    
    is_valid = len(warnings) == 0
    return is_valid, warnings

# Debug utility function
def debug_tree_parsing(block_text: str, files_always: Optional[Set[str]] = None, dirs_always: Optional[Set[str]] = None) -> dict:
    """
    Debug function to analyze tree parsing process.
    
    Args:
        block_text: ASCII tree text to parse
        files_always: Files always set
        dirs_always: Directories always set
        
    Returns:
        Dictionary with debug information
    """
    debug_info = {
        "input_lines": len(block_text.splitlines()) if block_text else 0,
        "parsed_entries": 0,
        "files_count": 0,
        "directories_count": 0,
        "validation_passed": False,
        "validation_warnings": [],
        "parsing_time_ms": 0
    }
    
    import time
    start_time = time.time()
    
    entries = parse_ascii_tree_block(block_text, files_always or set(), dirs_always or set())
    debug_info["parsed_entries"] = len(entries)
    
    # Count files vs directories
    for entry in entries:
        if is_probably_file(Path(entry).name, files_always or set(), dirs_always or set()):
            debug_info["files_count"] += 1
        else:
            debug_info["directories_count"] += 1
    
    # Validate
    is_valid, warnings = validate_parsed_tree(entries)
    debug_info["validation_passed"] = is_valid
    debug_info["validation_warnings"] = warnings
    
    debug_info["parsing_time_ms"] = round((time.time() - start_time) * 1000, 2)
    
    return debug_info