"""
Cache validation functions.
"""
import logging
from typing import Dict, Any
from datetime import datetime


def validate_cache_structure(cache_data: Dict[str, Any]) -> bool:
    """
    Fast cache structure validation.
    
    Args:
        cache_data: Cache data to validate
        
    Returns:
        Validation result
    """
    if not isinstance(cache_data, dict):
        return False
    
    # Quick basic validation
    if not cache_data:
        return True
    
    # Optional: Validate specific fields if they exist
    if 'version' in cache_data:
        if not isinstance(cache_data['version'], (int, str)):
            return False
    
    if 'timestamp' in cache_data:
        if not isinstance(cache_data['timestamp'], (int, float)):
            return False
    
    return True


from typing import Optional

def validate_cache_content(cache_data: Dict[str, Any], 
                          expected_structure: Optional[Dict[str, type]] = None) -> bool:
    """
    Validate cache content against expected structure.
    
    Args:
        cache_data: Cache data to validate
        expected_structure: Expected key-type mapping
        
    Returns:
        Validation result
    """
    if not validate_cache_structure(cache_data):
        return False
    
    if expected_structure:
        for key, expected_type in expected_structure.items():
            if key in cache_data and not isinstance(cache_data[key], expected_type):
                logging.warning(f"⚠️ Cache validation failed for key {key}")
                return False
    
    return True


def is_cache_fresh(timestamp: float, max_age_seconds: int) -> bool:
    """
    Check if cache entry is fresh based on timestamp.
    
    Args:
        timestamp: Cache timestamp
        max_age_seconds: Maximum age in seconds
        
    Returns:
        True if cache is fresh
    """
    current_time = datetime.now().timestamp()
    return (current_time - timestamp) <= max_age_seconds