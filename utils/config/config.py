from pathlib import Path
import json
import logging
from typing import Dict, Optional, Union, List
from functools import lru_cache
import os

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
    
    "default": "# TODO: implement\n",
}

# File detection + special cases with better categorization
SPECIAL_FILES = {
    # Build and dependency files
    "dockerfile", "makefile", "procfile",
    "package.json", "requirements.txt", "pipfile", "gemfile",
    "cargo.toml", "go.mod", "composer.json", "pom.xml",
    
    # Configuration files
    ".gitignore", ".eslintrc", ".editorconfig", ".prettierrc",
    ".env", ".env.example", ".env.local", ".env.production",
    "tsconfig.json", "webpack.config.js", "rollup.config.js",
    "vite.config.js", "jest.config.js", "babel.config.js",
    
    # Documentation
    "readme", "readme.md", "readme.txt", "contributing", "authors",
    "changelog", "changelog.md", "license", "license.md", "code_of_conduct",
    
    # Project-specific
    "firestore.rules", "docker-compose.yml", "docker-compose.yaml",
    ".travis.yml", "github/workflows", "gitlab-ci.yml",
    
    # Runtime and deployment
    "procfile", "manifest.yml", "app.yaml", "cloudbuild.yaml",
}

@lru_cache(maxsize=50)
def get_comment_prefix(ext: str) -> str:
    """
    Get comment prefix for file extension with caching.
    
    Args:
        ext: File extension including dot (e.g., ".py")
        
    Returns:
        Comment prefix string
    """
    ext = ext.lower().strip()
    
    comment_prefixes = {
        # Single-line comment styles
        ".py": "# ",
        ".sh": "# ",
        ".bash": "# ",
        ".zsh": "# ",
        ".ps1": "# ",
        ".yml": "# ",
        ".yaml": "# ",
        ".cfg": "# ",
        ".conf": "# ",
        ".txt": "# ",
        ".rb": "# ",
        ".pl": "# ",
        ".tcl": "# ",
        ".r": "# ",
        ".lua": "-- ",
        ".sql": "-- ",
        ".sqlite": "-- ",
        
        # C-style comments
        ".js": "// ",
        ".ts": "// ",
        ".tsx": "// ",
        ".jsx": "// ",
        ".java": "// ",
        ".go": "// ",
        ".rs": "// ",
        ".cpp": "// ",
        ".c": "// ",
        ".h": "// ",
        ".hpp": "// ",
        ".cs": "// ",
        ".php": "// ",
        ".swift": "// ",
        ".kt": "// ",
        ".scala": "// ",
        ".m": "// ",
        
        # Multi-line comment openers
        ".css": "/* ",
        ".scss": "/* ",
        ".sass": "/* ",
        ".less": "/* ",
        
        # HTML/XML comments
        ".html": "<!-- ",
        ".xml": "<!-- ",
        ".md": "<!-- ",
        
        # Special cases
        ".bat": "REM ",
        ".vim": "\" ",
        ".el": "; ",
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

def find_config_candidates(explicit_path: Optional[str] = None) -> List[Path]:
    """
    Generate list of candidate paths for configuration file.
    
    Args:
        explicit_path: Explicitly provided config path
        
    Returns:
        List of candidate paths in search order
    """
    candidates = []
    
    # 1. Explicit path (highest priority)
    if explicit_path:
        candidates.append(Path(explicit_path))
    
    # 2. Current working directory
    candidates.append(Path.cwd() / "generator.config.json")
    
    # 3. Script directory
    try:
        script_dir = Path(__file__).parent.parent.parent
        candidates.append(script_dir / "generator.config.json")
    except (NameError, AttributeError):
        pass
    
    # 4. User home directory (lowest priority)
    home_dir = Path.home()
    candidates.append(home_dir / ".config" / "generator.config.json")
    candidates.append(home_dir / ".generator.config.json")
    
    return candidates

def load_config_file(explicit_path: Optional[str] = None) -> Dict:
    """
    Load configuration JSON with comprehensive search and validation.
    
    Args:
        explicit_path: Explicit path to config file
        
    Returns:
        Configuration dictionary, empty if none found or invalid
    """
    candidates = find_config_candidates(explicit_path)
    
    for config_path in candidates:
        if not config_path or not config_path.exists():
            continue
            
        try:
            # Basic file validation
            if not config_path.is_file():
                logging.debug(f"⚠️ Config path is not a file: {config_path}")
                continue
                
            file_size = config_path.stat().st_size
            if file_size > 1024 * 1024:  # 1MB limit
                logging.warning(f"⚠️ Config file too large: {config_path} ({file_size} bytes)")
                continue
            
            # Read and parse
            content = config_path.read_text(encoding="utf-8")
            config_data = json.loads(content)
            
            if not isinstance(config_data, dict):
                logging.warning(f"⚠️ Config file must contain JSON object: {config_path}")
                continue
            
            logging.info(f"✅ Loaded configuration from: {config_path}")
            return config_data
            
        except json.JSONDecodeError as e:
            logging.warning(f"⚠️ Invalid JSON in config file {config_path}: {e}")
        except UnicodeDecodeError:
            logging.warning(f"⚠️ Invalid encoding in config file {config_path}")
        except PermissionError:
            logging.warning(f"⚠️ Permission denied reading config file {config_path}")
        except Exception as e:
            logging.warning(f"⚠️ Failed to load config file {config_path}: {e}")
    
    logging.debug("ℹ️ No valid configuration file found, using defaults")
    return {}

def merge_placeholders_from_file(placeholders_path: Optional[str] = None) -> bool:
    """
    Merge external JSON placeholders into EXT_COMMENT_PLACEHOLDER.
    
    Args:
        placeholders_path: Path to placeholders JSON file
        
    Returns:
        True if successfully merged, False otherwise
    """
    if not placeholders_path:
        return False
    
    try:
        placeholder_file = Path(placeholders_path)
        
        # Validate path
        if not placeholder_file.exists():
            logging.warning(f"⚠️ Placeholders file not found: {placeholders_path}")
            return False
        
        if not placeholder_file.is_file():
            logging.warning(f"⚠️ Placeholders path is not a file: {placeholders_path}")
            return False
        
        # Check file size
        file_size = placeholder_file.stat().st_size
        if file_size > 1024 * 1024:  # 1MB limit
            logging.warning(f"⚠️ Placeholders file too large: {file_size} bytes")
            return False
        
        # Read and parse
        content = placeholder_file.read_text(encoding="utf-8")
        data = json.loads(content)
        
        if not isinstance(data, dict):
            logging.warning("⚠️ Placeholders file must contain a JSON object")
            return False
        
        # Merge placeholders
        merged_count = 0
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                EXT_COMMENT_PLACEHOLDER[key] = value
                merged_count += 1
            else:
                logging.warning(f"⚠️ Skipping invalid placeholder entry: {key}")
        
        logging.info(f"✅ Loaded {merged_count} placeholders from {placeholders_path}")
        return merged_count > 0
        
    except json.JSONDecodeError as e:
        logging.warning(f"⚠️ Invalid JSON in placeholders file: {e}")
    except UnicodeDecodeError:
        logging.warning(f"⚠️ Invalid encoding in placeholders file: {placeholders_path}")
    except PermissionError:
        logging.warning(f"⚠️ Permission denied reading placeholders file: {placeholders_path}")
    except Exception as e:
        logging.warning(f"⚠️ Failed to load placeholders from {placeholders_path}: {e}")
    
    return False

def is_special_file(filename: str) -> bool:
    """
    Check if filename matches known special file patterns.
    
    Args:
        filename: Filename to check
        
    Returns:
        True if filename matches special file patterns
    """
    if not filename:
        return False
    
    name_lower = filename.lower().strip()
    
    # Exact matches
    if name_lower in SPECIAL_FILES:
        return True
    
    # Pattern matches
    if name_lower.startswith(".env") or name_lower.endswith(".config.js"):
        return True
    
    # Directory patterns
    if "/" in name_lower and any(special in name_lower for special in ["github/workflows", ".github/"]):
        return True
    
    return False

# Utility function for debugging configuration
def debug_config_loading(explicit_path: Optional[str] = None) -> Dict:
    """
    Debug function to analyze configuration loading process.
    
    Args:
        explicit_path: Explicit config path to test
        
    Returns:
        Dictionary with debug information
    """
    debug_info: Dict[str, Union[List[str], str, int, None]] = {
        "candidates": [],
        "loaded_from": None,
        "config_keys": [],
        "placeholder_count": len(EXT_COMMENT_PLACEHOLDER),
        "special_files_count": len(SPECIAL_FILES)
    }
    
    candidates = find_config_candidates(explicit_path)
    debug_info["candidates"] = [str(candidate) for candidate in candidates]
    
    config_data = load_config_file(explicit_path)
    if config_data:
        debug_info["loaded_from"] = next((str(candidate) for candidate in candidates if candidate.exists()), None)
        debug_info["config_keys"] = list(config_data.keys())
    
    return debug_info