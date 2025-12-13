from functools import lru_cache
from typing import Dict

@lru_cache(maxsize=100)
def get_comment_prefix(ext: str) -> str:
    """
    Get comment prefix for file extension with caching.
    
    Args:
        ext: File extension without leading dot (e.g., "py") or empty string for extensionless files
        
    Returns:
        Comment prefix string
    """
    ext = ext.lower().strip().lstrip('.') if ext else ""
    comment_prefixes: Dict[str, str] = {
        # Single-line comment styles
        "py": "# ",
        "sh": "# ",
        "bash": "# ",
        "zsh": "# ",
        "ps1": "# ",
        "yml": "# ",
        "yaml": "# ",
        "cfg": "# ",
        "conf": "# ",
        "txt": "# ",
        "rb": "# ",
        "pl": "# ",
        "tcl": "# ",
        "r": "# ",
        "lua": "-- ",
        "sql": "-- ",
        "sqlite": "-- ",
        
        # C-style comments
        "js": "// ",
        "ts": "// ",
        "tsx": "// ",
        "jsx": "// ",
        "java": "// ",
        "go": "// ",
        "rs": "// ",
        "cpp": "// ",
        "c": "// ",
        "h": "// ",
        "hpp": "// ",
        "cs": "// ",
        "php": "// ",
        "swift": "// ",
        "kt": "// ",
        "scala": "// ",
        "m": "% ",
        "ino": "// ",
        
        # Multi-line comment openers
        "css": "/* ",
        "scss": "/* ",
        "sass": "/* ",
        "less": "/* ",
        
        # HTML/XML comments
        "html": "<!-- ",
        "xml": "<!-- ",
        "md": "<!-- ",
        
        # Special cases
        "bat": "REM ",
        "vim": "\" ",
        "el": "; ",
        
        # Extensionless or special files
        "json": "//",  
        "": "# ",  # Default for extensionless files (e.g., README, .gitignore)
        "gitignore": "# ",
        "dockerfile": "# ",
    }
    
    return comment_prefixes.get(ext, "# ")

def get_comment_suffix(ext: str) -> str:
    """
    Get comment suffix for file extension.
    
    Args:
        ext: File extension including dot
        
    Returns:
        Comment suffix string
    """
    ext = ext.lower().strip()
    
    if ext in {".css", ".scss", ".sass", ".less"}:
        return " */"
    elif ext in {".html", ".xml", ".md"}:
        return " -->"
    else:
        return ""