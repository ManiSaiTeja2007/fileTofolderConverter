from pathlib import Path
import re
import logging
from typing import Optional, List, Set

# Pre-compiled regex patterns for performance
WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:\\", re.IGNORECASE)
WINDOWS_UNC_PATTERN = re.compile(r"^\\\\", re.IGNORECASE)
PROTOCOL_PATTERN = re.compile(r"^[a-z]+://", re.IGNORECASE)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
RESERVED_NAMES_PATTERN = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]|CLOCK\$)$", 
    re.IGNORECASE
)

# Common dangerous/reserved names
RESERVED_NAMES: Set[str] = {
    "CON", "PRN", "AUX", "NUL", 
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    "CLOCK$"
}

# Common dangerous extensions
DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".sh", ".bin", ".app", ".dmg", ".pkg",
    ".msi", ".scr", ".com", ".jar", ".war", ".ear", ".apk", ".ipa"
}

def validate_entry_path(entry: str, allow_dangerous_extensions: bool = False) -> Optional[str]:
    """
    Validate that a path entry is safe for file system operations.
    
    Args:
        entry: Path string to validate
        allow_dangerous_extensions: If True, allow potentially dangerous file extensions
        
    Returns:
        None if path is safe, otherwise error message string
    """
    # Input validation
    if not isinstance(entry, str):
        return "Path must be a string"
    
    if not entry or not entry.strip():
        return "Empty path"
    
    entry = entry.strip()
    
    # Check for empty after stripping
    if not entry:
        return "Empty path after stripping whitespace"
    
    # Check for control characters
    if CONTROL_CHAR_PATTERN.search(entry):
        return "Control characters not allowed in paths"
    
    # Check for absolute paths
    if entry.startswith(("/", "\\")):
        return "Absolute paths are not allowed"
    
    # Check for Windows drive letters
    if WINDOWS_DRIVE_PATTERN.match(entry):
        return "Absolute Windows paths not allowed"
    
    # Check for Windows UNC paths
    if WINDOWS_UNC_PATTERN.match(entry):
        return "Windows UNC paths not allowed"
    
    # Check for URL protocols
    if PROTOCOL_PATTERN.match(entry):
        return "URL protocols not allowed in paths"
    
    # Check for parent directory traversal
    try:
        path = Path(entry)
        if ".." in path.parts:
            return "Parent directory traversal ('..') not allowed"
        
        # Check each path component
        for part in path.parts:
            if not part or part == ".":
                continue
            
            # Check for reserved names (Windows)
            if RESERVED_NAMES_PATTERN.match(part):
                return f"Reserved name not allowed: {part}"
            
            # Check for trailing spaces or dots (Windows issue)
            if part.endswith((" ", ".")):
                return "Trailing spaces or dots not allowed in path components"
            
            # Check for invalid characters in filenames
            if any(char in part for char in ['<', '>', ':', '"', '|', '?', '*']):
                return f"Invalid characters in path component: {part}"
    
    except Exception as e:
        return f"Invalid path structure: {e}"
    
    # Check for dangerous file extensions (optional)
    if not allow_dangerous_extensions:
        extension = Path(entry).suffix.lower()
        if extension in DANGEROUS_EXTENSIONS:
            return f"Potentially dangerous file extension: {extension}"
    
    # Check for excessive path length (Windows limit is 260 chars, but be conservative)
    if len(entry) > 200:
        return "Path too long (max 200 characters)"
    
    # Check for excessive depth
    if len(Path(entry).parts) > 20:
        return "Path too deep (max 20 levels)"
    
    return None

def validate_multiple_paths(entries: List[str], allow_dangerous_extensions: bool = False) -> List[tuple[str, Optional[str]]]:
    """
    Validate multiple path entries at once.
    
    Args:
        entries: List of path strings to validate
        allow_dangerous_extensions: Whether to allow dangerous extensions
        
    Returns:
        List of tuples (entry, error_message)
    """
    if not entries:
        return []
    
    results = []
    for entry in entries:
        error = validate_entry_path(entry, allow_dangerous_extensions)
        results.append((entry, error))
    
    return results

def safe_path_join(base_dir: Path, *path_parts: str) -> Optional[Path]:
    """
    Safely join paths and validate the result doesn't escape the base directory.
    
    Args:
        base_dir: Base directory to join paths under
        *path_parts: Path components to join
        
    Returns:
        Safe Path object or None if validation fails
    """
    try:
        # Join and normalize the path
        full_path = base_dir.joinpath(*path_parts).resolve()
        base_resolved = base_dir.resolve()
        
        # Ensure the result is within the base directory
        try:
            full_path.relative_to(base_resolved)
        except ValueError:
            return None  # Path escapes base directory
        
        return full_path
        
    except Exception as e:
        logging.debug(f"⚠️ Error in safe_path_join: {e}")
        return None

def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a filename by removing dangerous characters.
    
    Args:
        filename: Original filename
        replacement: Character to replace dangerous characters with
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return ""
    
    # Remove control characters
    sanitized = CONTROL_CHAR_PATTERN.sub(replacement, filename)
    
    # Remove Windows reserved characters
    for char in ['<', '>', ':', '"', '|', '?', '*', '\\', '/']:
        sanitized = sanitized.replace(char, replacement)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip().strip('.')
    
    # Ensure not empty after sanitization
    if not sanitized:
        return "unnamed_file"
    
    # Check for reserved names and modify if found
    base_name = Path(sanitized).stem
    if RESERVED_NAMES_PATTERN.match(base_name):
        sanitized = f"_{sanitized}"
    
    return sanitized

def is_path_safe_for_creation(entry: str, base_dir: Path) -> bool:
    """
    Check if a path is safe to create within a base directory.
    
    Args:
        entry: Relative path to check
        base_dir: Base directory to check against
        
    Returns:
        True if path is safe to create
    """
    if not base_dir.exists() or not base_dir.is_dir():
        return False
    
    error = validate_entry_path(entry)
    if error:
        return False
    
    safe_path = safe_path_join(base_dir, entry)
    return safe_path is not None

# Debug utility
def debug_path_validation(entries: List[str]) -> dict:
    """
    Debug function to analyze path validation.
    
    Args:
        entries: List of paths to validate
        
    Returns:
        Dictionary with validation results
    """
    debug_info = {
        "total_entries": len(entries),
        "safe_entries": 0,
        "unsafe_entries": 0,
        "common_issues": {},
        "validation_results": []
    }
    
    for entry in entries:
        error = validate_entry_path(entry)
        is_safe = error is None
        
        if is_safe:
            debug_info["safe_entries"] += 1
        else:
            debug_info["unsafe_entries"] += 1
            # This line correctly counts the occurrences of each error type
            debug_info["common_issues"][error] = debug_info["common_issues"].get(error, 0) + 1
        
        # --- FIX IS HERE ---
        # Complete the dictionary being appended
        debug_info["validation_results"].append({
            "entry": entry,
            "is_safe": is_safe,
            "error": error
        })
    
    return debug_info



'''
    for entry in entries:
        error = validate_entry_path(entry)
        is_safe = error is None
        
        if is_safe:
            debug_info["safe_entries"] += 1
        else:
            debug_info["unsafe_entries"] += 1
            # This line correctly counts the occurrences of each error type
            debug_info["common_issues"][error] = debug_info["common_issues"].get(error, 0) + 1
        
        # --- FIX IS HERE ---
        # Complete the dictionary being appended
        debug_info["validation_results"].append({
            "entry": entry,
            "is_safe": is_safe,
            "error": error
        })
'''