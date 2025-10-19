from pathlib import Path
import json
import logging
from typing import Dict, Any, Optional
import hashlib

def generate_cache_key(content: str) -> str:
    """
    Generate a deterministic cache key for content.
    
    Args:
        content: Content to generate key for
        
    Returns:
        MD5 hash of the content
    """
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def validate_cache_structure(cache_data: Dict[str, Any]) -> bool:
    """
    Validate the structure of cache data.
    
    Args:
        cache_data: Cache data to validate
        
    Returns:
        True if cache structure is valid
    """
    if not isinstance(cache_data, dict):
        return False
    
    # Check for required fields if they exist
    if 'version' in cache_data and not isinstance(cache_data['version'], (int, str)):
        return False
    
    if 'timestamp' in cache_data and not isinstance(cache_data['timestamp'], (int, float)):
        return False
    
    return True

def safe_json_loads(json_string: str) -> Optional[Dict[str, Any]]:
    """
    Safely parse JSON string with comprehensive error handling.
    
    Args:
        json_string: JSON string to parse
        
    Returns:
        Parsed dictionary or None if failed
    """
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        logging.warning(f"⚠️ Invalid JSON in cache file: {e}")
        return None
    except TypeError as e:
        logging.warning(f"⚠️ Type error parsing cache JSON: {e}")
        return None
    except Exception as e:
        logging.warning(f"⚠️ Unexpected error parsing cache JSON: {e}")
        return None

def load_cache(cache_file: Path, max_size_mb: int = 10) -> Dict[str, Any]:
    """
    Load cache data from file with comprehensive validation and error handling.
    
    Args:
        cache_file: Path to the cache file
        max_size_mb: Maximum allowed cache file size in MB (default: 10MB)
        
    Returns:
        Cache data as dictionary, empty dict if loading fails
    """
    # Input validation
    if not isinstance(cache_file, Path):
        logging.warning("⚠️ Invalid cache file path type")
        return {}
    
    if not cache_file.exists():
        logging.debug(f"ℹ️ Cache file does not exist: {cache_file}")
        return {}
    
    try:
        # Check file size before reading
        file_size = cache_file.stat().st_size
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            logging.warning(f"⚠️ Cache file too large: {file_size} bytes > {max_size_bytes} bytes limit")
            return {}
        
        if file_size == 0:
            logging.debug("ℹ️ Cache file is empty")
            return {}
        
        # Read file with encoding handling
        try:
            content = cache_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            logging.warning(f"⚠️ Cache file has invalid UTF-8 encoding: {cache_file}")
            return {}
        
        # Parse JSON safely
        cache_data = safe_json_loads(content)
        if cache_data is None:
            return {}
        
        # Validate cache structure
        if not validate_cache_structure(cache_data):
            logging.warning("⚠️ Cache file has invalid structure")
            return {}
        
        logging.debug(f"✅ Successfully loaded cache from {cache_file} ({len(cache_data)} entries)")
        return cache_data
        
    except PermissionError:
        logging.warning(f"⚠️ Permission denied reading cache file: {cache_file}")
        return {}
    except FileNotFoundError:
        logging.debug(f"ℹ️ Cache file disappeared during reading: {cache_file}")
        return {}
    except Exception as e:
        logging.warning(f"⚠️ Unexpected error loading cache from {cache_file}: {e}")
        return {}

def save_cache(cache_file: Path, cache_data: Dict[str, Any], create_backup: bool = True) -> bool:
    """
    Save cache data to file with atomic write and backup support.
    
    Args:
        cache_file: Path to save cache file
        cache_data: Cache data to save
        create_backup: Whether to create backup of existing file
        
    Returns:
        True if save was successful
    """
    if not isinstance(cache_file, Path):
        logging.warning("⚠️ Invalid cache file path for saving")
        return False
    
    if not isinstance(cache_data, dict):
        logging.warning("⚠️ Invalid cache data type for saving")
        return False
    
    try:
        # Create parent directories if needed
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create backup of existing file if requested
        backup_file = None
        if create_backup and cache_file.exists():
            backup_file = cache_file.with_suffix(cache_file.suffix + '.bak')
            try:
                cache_file.rename(backup_file)
                logging.debug(f"✅ Created cache backup: {backup_file}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to create cache backup: {e}")
        
        # Write to temporary file first (atomic operation)
        temp_file = cache_file.with_suffix(cache_file.suffix + '.tmp')
        
        try:
            # Serialize with pretty printing for readability
            json_content = json.dumps(cache_data, indent=2, ensure_ascii=False)
            temp_file.write_text(json_content, encoding='utf-8')
            
            # Atomic replace
            temp_file.replace(cache_file)
            logging.debug(f"✅ Successfully saved cache to {cache_file}")
            return True
            
        except Exception as e:
            # Clean up temp file on failure
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            
            # Restore backup if we created one
            if backup_file and backup_file.exists():
                try:
                    backup_file.replace(cache_file)
                    logging.debug("✅ Restored cache from backup after failed save")
                except Exception as restore_error:
                    logging.warning(f"⚠️ Failed to restore cache backup: {restore_error}")
            
            raise e
            
    except PermissionError:
        logging.warning(f"⚠️ Permission denied writing cache file: {cache_file}")
        return False
    except Exception as e:
        logging.warning(f"⚠️ Failed to save cache to {cache_file}: {e}")
        return False

def clear_cache(cache_file: Path) -> bool:
    """
    Clear cache file.
    
    Args:
        cache_file: Path to cache file to clear
        
    Returns:
        True if cleared successfully
    """
    try:
        if cache_file.exists():
            cache_file.unlink()
            logging.debug(f"✅ Cleared cache file: {cache_file}")
        return True
    except Exception as e:
        logging.warning(f"⚠️ Failed to clear cache file {cache_file}: {e}")
        return False

def get_cache_info(cache_file: Path) -> Dict[str, Any]:
    """
    Get information about cache file.
    
    Args:
        cache_file: Path to cache file
        
    Returns:
        Dictionary with cache information
    """
    info = {
        'exists': False,
        'size_bytes': 0,
        'entry_count': 0,
        'last_modified': None
    }
    
    if cache_file.exists():
        try:
            info['exists'] = True
            info['size_bytes'] = cache_file.stat().st_size
            info['last_modified'] = int(cache_file.stat().st_mtime)
            
            # Try to count entries without full validation
            cache_data = load_cache(cache_file)
            if cache_data:
                info['entry_count'] = len(cache_data)
                
        except Exception as e:
            logging.debug(f"⚠️ Could not get full cache info: {e}")
    
    return info

# Utility function for debugging cache operations
def debug_cache_operations(cache_file: Path) -> Dict[str, Any]:
    """
    Debug function to analyze cache operations.
    
    Args:
        cache_file: Cache file to analyze
        
    Returns:
        Dictionary with debug information
    """
    debug_info = {
        'cache_file': str(cache_file),
        'file_exists': cache_file.exists(),
        'load_success': False,
        'cache_info': {},
        'test_save_success': False
    }
    
    if cache_file.exists():
        debug_info['cache_info'] = get_cache_info(cache_file)
        
        # Test loading
        test_data = load_cache(cache_file)
        debug_info['load_success'] = bool(test_data)
        debug_info['loaded_entries'] = len(test_data) if test_data else 0
        
        # Test saving (if we have data)
        if test_data:
            debug_info['test_save_success'] = save_cache(cache_file, test_data)
    
    return debug_info