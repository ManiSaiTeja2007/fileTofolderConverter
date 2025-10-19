from pathlib import Path
from typing import Optional, Set
import logging

from utils.config.config import SPECIAL_FILES, is_special_file

def is_probably_file(name: str, files_always: Optional[Set] = None, dirs_always: Optional[Set] = None) -> bool:
    """
    Heuristic to decide whether a path segment is a file.
    Enhanced with robust error handling and improved detection logic.
    
    Args:
        name: File or directory name to check
        files_always: Set of names to always treat as files
        dirs_always: Set of names to always treat as directories
        
    Returns:
        True if the name is probably a file
    """
    # Input validation
    if not name or not isinstance(name, str):
        return False
    
    try:
        name = name.strip()
        if not name:
            return False
        
        # Normalize inputs
        files_always = set(x.lower() for x in (files_always or set()))
        dirs_always = set(x.lower() for x in (dirs_always or set()))
        
        base = Path(name).name
        base_lower = base.lower()
        
        # Explicit directory indicators
        if name.endswith("/") or name.endswith("\\"):
            return False
        
        # Explicit directory overrides (highest priority)
        if base_lower in dirs_always:
            return False
        
        # Explicit file overrides (high priority)
        if base_lower in files_always:
            return True
        
        # Special file detection using our enhanced function
        if is_special_file(base):
            return True
        
        # Common file extensions heuristic
        if "." in base and len(base) > 1:
            # Avoid false positives like hidden directories (.git, .vscode)
            if base.startswith(".") and base.count(".") == 1:
                # Could be hidden file or directory, use additional checks
                if base_lower in {".git", ".vscode", ".idea", ".venv", "node_modules"}:
                    return False
                return True  # Most dotfiles are files
            
            # Regular files with extensions
            return True
        
        # Common file-like names without extensions
        file_like_names = {
            "dockerfile", "makefile", "procfile", "license", "readme", 
            "changelog", "contributing", "authors", "code_of_conduct"
        }
        if base_lower in file_like_names:
            return True
        
        # Default to directory for ambiguous cases
        return False
        
    except Exception as e:
        logging.warning(f"⚠️ Error in file detection for '{name}': {e}")
        # Conservative fallback: treat as directory to avoid file creation errors
        return False

def debug_file_detection(name: str, files_always: Optional[Set] = None, dirs_always: Optional[Set] = None) -> dict:
    """
    Debug function to analyze file detection logic.
    
    Args:
        name: Name to analyze
        files_always: Files always set
        dirs_always: Directories always set
        
    Returns:
        Dictionary with detection details
    """
    debug_info = {
        "input": name,
        "base_name": Path(name).name if name else None,
        "is_special_file": False,
        "in_files_always": False,
        "in_dirs_always": False,
        "has_extension": False,
        "final_decision": False,
        "reason": ""
    }
    
    if name:
        base = Path(name).name
        base_lower = base.lower()
        
        debug_info["is_special_file"] = is_special_file(base)
        debug_info["in_files_always"] = base_lower in (set(x.lower() for x in (files_always or set())))
        debug_info["in_dirs_always"] = base_lower in (set(x.lower() for x in (dirs_always or set())))
        debug_info["has_extension"] = "." in base and len(base) > 1
        
        # Simulate decision logic
        result = is_probably_file(name, files_always, dirs_always)
        debug_info["final_decision"] = result
        
        # Determine reason
        if name.endswith("/"):
            debug_info["reason"] = "ends with slash"
        elif debug_info["in_dirs_always"]:
            debug_info["reason"] = "in dirs_always set"
        elif debug_info["in_files_always"]:
            debug_info["reason"] = "in files_always set"
        elif debug_info["is_special_file"]:
            debug_info["reason"] = "special file detected"
        elif debug_info["has_extension"]:
            debug_info["reason"] = "has file extension"
        else:
            debug_info["reason"] = "default to directory"
    
    return debug_info