from typing import Dict

# Default placeholders by extension with more comprehensive coverage
EXT_COMMENT_PLACEHOLDER: Dict[str, str] = {
    # Programming languages
    ".py": "# TODO: implement\n",
    ".js": "// TODO: implement\n",
    ".ts": "// TODO: implement\n",
    ".tsx": "// TODO: implement\n",
    ".jsx": "// TODO: implement\n",
    ".java": "// TODO: implement\n",
    ".go": "// TODO: implement\n",
    ".rs": "// TODO: implement\n",
    ".cpp": "// TODO: implement\n",
    ".c": "// TODO: implement\n",
    ".h": "// TODO: implement\n",
    ".hpp": "// TODO: implement\n",
    ".cs": "// TODO: implement\n",
    ".php": "// TODO: implement\n",
    ".rb": "# TODO: implement\n",
    ".swift": "// TODO: implement\n",
    ".kt": "// TODO: implement\n",
    
    # Scripting and config
    ".sh": "# TODO: implement\n",
    ".bash": "# TODO: implement\n",
    ".zsh": "# TODO: implement\n",
    ".ps1": "# TODO: implement\n",
    ".bat": "REM TODO: implement\n",
    ".cfg": "# TODO: implement\n",
    ".conf": "# TODO: implement\n",
    
    # Data formats
    ".yml": "# TODO: implement\n",
    ".yaml": "# TODO: implement\n",
    ".json": "{\n  \"//\": \"TODO: fill\"\n}\n",
    ".xml": "<!-- TODO: implement -->\n",
    ".csv": "# TODO: fill data\n",
    ".toml": "# TODO: implement\n",
    
    # Documentation
    ".md": "<!-- TODO: fill -->\n",
    ".rst": ".. TODO: fill\n",
    ".txt": "# TODO: fill\n",
    
    # Web technologies
    ".html": "<!-- TODO: implement -->\n",
    ".css": "/* TODO: implement */\n",
    ".scss": "/* TODO: implement */\n",
    ".sass": "/* TODO: implement */\n",
    ".less": "/* TODO: implement */\n",
    
    # Database
    ".sql": "-- TODO: implement\n",
    ".sqlite": "-- TODO: implement\n",
    
    ".m":"% TODO: implement\n",
    "default": "# TODO: implement\n",
}

def get_default_placeholder(ext: str) -> str:
    """
    Get appropriate placeholder content for file extension.
    
    Args:
        ext: File extension including dot
        
    Returns:
        Placeholder content string
    """
    ext = ext.lower().strip()
    
    # Special handling for common file types
    if ext == ".json":
        return '{\n  "//": "TODO: Add configuration"\n}\n'
    elif ext == ".yml" or ext == ".yaml":
        return "# TODO: Add configuration\n"
    elif ext == ".md":
        return "<!-- TODO: Add documentation -->\n"
    elif ext == ".html":
        return "<!-- TODO: Add HTML content -->\n"
    elif ext == ".css":
        return "/* TODO: Add styles */\n"
    elif ext == ".py":
        return '"""TODO: Add module docstring"""\n\n# TODO: Implement functionality\n'
    elif ext == ".sh":
        return "#!/bin/bash\n\n# TODO: Implement script\n"
    
    return EXT_COMMENT_PLACEHOLDER.get(ext, EXT_COMMENT_PLACEHOLDER["default"])