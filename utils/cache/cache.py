"""
Main cache interface combining all modules.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .core import CacheCore
from .utils import generate_cache_key, get_cache_info, debug_cache_operations
from .validation import validate_cache_content, is_cache_fresh


class CacheManager:
    """
    High-performance cache manager with modular components.
    """
    
    def __init__(self, cache_dir: Path = Path('.cache'), 
                 max_size_mb: int = 10,
                 use_mmap: bool = True,
                 auto_create_dirs: bool = True):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Cache directory path
            max_size_mb: Maximum cache file size in MB
            use_mmap: Use memory mapping for large files
            auto_create_dirs: Auto-create cache directory
        """
        self.cache_dir = Path(cache_dir)
        self.max_size_mb = max_size_mb
        self.use_mmap = use_mmap
        
        if auto_create_dirs:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize core cache operations
        self.core = CacheCore(max_size_mb=max_size_mb, use_mmap=use_mmap)
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'loads': 0,
            'saves': 0
        }
    
    def get_file_path(self, cache_name: str) -> Path:
        """Get full path for cache file."""
        return self.cache_dir / f"{cache_name}.json"
    
    def load(self, cache_name: str) -> Dict[str, Any]:
        """
        Load cache by name.
        
        Args:
            cache_name: Name of cache to load
            
        Returns:
            Cache data
        """
        cache_file = self.get_file_path(cache_name)
        data = self.core.load_cache(cache_file)
        self.stats['loads'] += 1
        self.stats['misses' if not data else 'hits'] += 1
        return data or {}
    
    def save(self, cache_name: str, cache_data: Dict[str, Any], 
             create_backup: bool = True, atomic_write: bool = True) -> bool:
        """
        Save cache by name.
        
        Args:
            cache_name: Cache name
            cache_data: Data to save
            create_backup: Create backup file
            atomic_write: Use atomic operations
            
        Returns:
            Success status
        """
        cache_file = self.get_file_path(cache_name)
        success = self.core.save_cache(cache_file, cache_data, 
                                     create_backup, atomic_write)
        if success:
            self.stats['saves'] += 1
        return success
    
    def clear(self, cache_name: str) -> bool:
        """Clear specific cache."""
        cache_file = self.get_file_path(cache_name)
        return self.core.clear_cache(cache_file)
    
    def clear_all(self) -> bool:
        """Clear all caches in cache directory."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            return True
        except Exception as e:
            logging.warning(f"⚠️ Clear all failed: {e}")
            return False
    
    def get_info(self, cache_name: str) -> Dict[str, Any]:
        """Get cache information."""
        cache_file = self.get_file_path(cache_name)
        return get_cache_info(cache_file)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_ratio = (self.stats['hits'] / (self.stats['hits'] + self.stats['misses']) 
                    if (self.stats['hits'] + self.stats['misses']) > 0 else 0)
        
        return {
            **self.stats,
            'hit_ratio': hit_ratio,
            'cache_dir': str(self.cache_dir)
        }
    
    def debug(self, cache_name: str) -> Dict[str, Any]:
        """Debug cache operations."""
        cache_file = self.get_file_path(cache_name)
        return debug_cache_operations(cache_file)


# Global cache manager instance
_default_manager: Optional[CacheManager] = None

def get_default_cache() -> CacheManager:
    """Get or create default cache manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = CacheManager()
    return _default_manager

def set_default_cache(manager: CacheManager) -> None:
    """Set default cache manager."""
    global _default_manager
    _default_manager = manager