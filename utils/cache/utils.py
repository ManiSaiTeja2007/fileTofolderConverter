"""
Utility functions for cache operations.
"""
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any
import os


def generate_cache_key(content: str, algorithm: str = 'md5') -> str:
    """
    Generate deterministic cache key with choice of algorithm.
    
    Args:
        content: Content to hash
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256')
        
    Returns:
        Hash string
    """
    if algorithm == 'md5':
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(content.encode('utf-8')).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def get_cache_info(cache_file: Path) -> Dict[str, Any]:
    """
    Get cache file information with performance optimizations.
    
    Args:
        cache_file: Cache file path
        
    Returns:
        Cache information dictionary
    """
    info = {
        'exists': False,
        'size_bytes': 0,
        'entry_count': 0,
        'last_modified': None
    }
    
    try:
        if cache_file.exists():
            stat = cache_file.stat()
            info.update({
                'exists': True,
                'size_bytes': stat.st_size,
                'last_modified': int(stat.st_mtime)
            })
            
            # Fast entry count estimation for large files
            if stat.st_size > 0:
                info['entry_count'] = estimate_entry_count(cache_file)
                
    except OSError as e:
        logging.debug(f"⚠️ Cache info error: {e}")
    
    return info


def estimate_entry_count(cache_file: Path, sample_size: int = 8192) -> int:
    """
    Estimate number of entries in cache file without full parsing.
    
    Args:
        cache_file: Cache file to analyze
        sample_size: Bytes to sample for estimation
        
    Returns:
        Estimated entry count
    """
    try:
        with open(cache_file, 'rb') as f:
            # Read first part of file
            sample = f.read(sample_size).decode('utf-8', errors='ignore')
            
            # Count occurrences of common patterns
            if '"' in sample:
                # Count top-level keys (rough estimate)
                return sample.count('":')  
            else:
                return sample.count(':')
                
    except Exception:
        return 0


def debug_cache_operations(cache_file: Path) -> Dict[str, Any]:
    """
    Debug cache operations with performance metrics.
    
    Args:
        cache_file: Cache file to debug
        
    Returns:
        Debug information
    """
    import time
    
    debug_info = {
        'cache_file': str(cache_file),
        'file_exists': cache_file.exists(),
        'load_performance': 0,
        'save_performance': 0,
        'cache_info': {}
    }
    
    if cache_file.exists():
        # Test load performance
        start_time = time.time()
        from .core import CacheCore
        core = CacheCore()
        test_data = core.load_cache(cache_file)
        debug_info['load_performance'] = time.time() - start_time
        
        debug_info['load_success'] = bool(test_data)
        debug_info['loaded_entries'] = len(test_data) if test_data else 0
        debug_info['cache_info'] = get_cache_info(cache_file)
        
        # Test save performance if we have data
        if test_data:
            start_time = time.time()
            debug_info['test_save_success'] = core.save_cache(
                cache_file, test_data, create_backup=False
            )
            debug_info['save_performance'] = time.time() - start_time
    
    return debug_info