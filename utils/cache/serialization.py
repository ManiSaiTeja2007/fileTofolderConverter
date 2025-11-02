"""
Optimized JSON serialization/deserialization for cache operations.
"""
import json
import logging
from typing import Dict, Any, Optional
import ujson  # type: ignore # Fast JSON library


def fast_json_load(json_string: str) -> Optional[Dict[str, Any]]:
    """
    Ultra-fast JSON parsing with ujson fallback to standard json.
    
    Args:
        json_string: JSON string to parse
        
    Returns:
        Parsed dictionary or None
    """
    try:
        # Try ujson first (significantly faster)
        return ujson.loads(json_string)
    except (ImportError, Exception):
        try:
            # Fallback to standard json with optimizations
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logging.debug(f"⚠️ JSON parse error: {e}")
            return None


def fast_json_dump(data: Dict[str, Any], indent: Optional[int] = None) -> str:
    """
    Optimized JSON serialization.
    
    Args:
        data: Data to serialize
        indent: Indentation for pretty printing
        
    Returns:
        JSON string
    """
    try:
        # Try ujson first
        if indent:
            return ujson.dumps(data, indent=indent, ensure_ascii=False)
        else:
            return ujson.dumps(data, ensure_ascii=False)
    except (ImportError, Exception):
        # Fallback to standard json
        separators = (',', ':') if not indent else None
        return json.dumps(data, indent=indent, ensure_ascii=False, 
                         separators=separators)


def optimized_json_dump(data: Dict[str, Any]) -> str:
    """
    Highly optimized JSON dump for cache storage (no pretty printing).
    
    Args:
        data: Data to serialize
        
    Returns:
        Compact JSON string
    """
    try:
        return ujson.dumps(data, ensure_ascii=False)
    except (ImportError, Exception):
        return json.dumps(data, ensure_ascii=False, separators=(',', ':'))