from pathlib import Path
import json
import logging
from typing import Dict, Optional, Union, List
from .comment_placeholders import EXT_COMMENT_PLACEHOLDER
from .special_files import SPECIAL_FILES, is_special_file

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