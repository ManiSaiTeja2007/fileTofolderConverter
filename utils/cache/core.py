"""
Core cache operations with performance optimizations.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import os
import mmap

from .serialization import fast_json_load, fast_json_dump
from .validation import validate_cache_structure
from .backup import create_backup, restore_backup


class CacheCore:
    """High-performance core cache operations."""
    
    def __init__(self, max_size_mb: int = 10, use_mmap: bool = True):
        self.max_size_mb = max_size_mb
        self.use_mmap = use_mmap
        self.max_size_bytes = max_size_mb * 1024 * 1024
    
    def load_cache(self, cache_file: Path) -> Dict[str, Any]:
        """
        Load cache data with performance optimizations.
        
        Args:
            cache_file: Path to cache file
            
        Returns:
            Cache data dictionary
        """
        if not isinstance(cache_file, Path):
            logging.warning("⚠️ Invalid cache file path type")
            return {}
        
        if not cache_file.exists():
            return {}
        
        try:
            # Fast size check using os.stat (faster than Path.stat())
            file_size = os.stat(cache_file).st_size
            
            if file_size > self.max_size_bytes:
                logging.warning(f"⚠️ Cache file too large: {file_size} bytes")
                return {}
            
            if file_size == 0:
                return {}
            
            # Use mmap for large files for better performance
            if self.use_mmap and file_size > 1024:  # Use mmap for files > 1KB
                return self._load_with_mmap(cache_file, file_size)
            else:
                return self._load_direct(cache_file)
                
        except (PermissionError, FileNotFoundError, OSError) as e:
            logging.debug(f"⚠️ OS error loading cache: {e}")
            return {}
        except Exception as e:
            logging.warning(f"⚠️ Unexpected error loading cache: {e}")
            return {}
    
    def _load_with_mmap(self, cache_file: Path, file_size: int) -> Dict[str, Any]:
        """Load cache using memory mapping for better performance."""
        try:
            with open(cache_file, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    # Decode directly from memory map
                    content = mm.read().decode('utf-8')
                    cache_data = fast_json_load(content)
                    
                    if cache_data and validate_cache_structure(cache_data):
                        return cache_data
                    return {}
        except Exception as e:
            logging.debug(f"⚠️ MMap load failed, falling back to direct: {e}")
            return self._load_direct(cache_file)
    
    def _load_direct(self, cache_file: Path) -> Dict[str, Any]:
        """Direct file loading with optimized reading."""
        try:
            # Read in binary mode and decode (often faster for large files)
            content = cache_file.read_bytes().decode('utf-8')
            cache_data = fast_json_load(content)
            
            if cache_data and validate_cache_structure(cache_data):
                return cache_data
            return {}
        except UnicodeDecodeError:
            logging.warning(f"⚠️ Cache file encoding error: {cache_file}")
            return {}
        except Exception as e:
            logging.debug(f"⚠️ Direct load failed: {e}")
            return {}
    
    def save_cache(self, cache_file: Path, cache_data: Dict[str, Any], 
                   create_backup_flag: bool = True, atomic_write: bool = True) -> bool:
        """
        Save cache data with performance optimizations.
        
        Args:
            cache_file: Target cache file path
            cache_data: Data to save
            create_backup_flag: Whether to create backup
            atomic_write: Use atomic file operations
            
        Returns:
            Success status
        """
        if not isinstance(cache_data, dict):
            return False
        
        try:
            # Create parent directories
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup if requested
            backup_created = False
            if create_backup_flag and cache_file.exists():
                backup_created = create_backup(cache_file)
            
            # Use atomic write for safety, direct write for speed
            if atomic_write:
                success = self._atomic_save(cache_file, cache_data)
            else:
                success = self._direct_save(cache_file, cache_data)
            
            if not success and backup_created:
                restore_backup(cache_file)
            
            return success
            
        except Exception as e:
            logging.warning(f"⚠️ Save cache failed: {e}")
            return False
    
    def _atomic_save(self, cache_file: Path, cache_data: Dict[str, Any]) -> bool:
        """Atomic save using temporary file."""
        temp_file = cache_file.with_suffix(cache_file.suffix + '.tmp')
        
        try:
            # Write to temp file
            if self._direct_save(temp_file, cache_data):
                # Atomic replace
                os.replace(temp_file, cache_file)
                return True
            return False
        except Exception as e:
            # Cleanup temp file
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass
            raise e
    
    def _direct_save(self, cache_file: Path, cache_data: Dict[str, Any]) -> bool:
        """Direct file save without atomic operations (faster)."""
        try:
            json_content = fast_json_dump(cache_data)
            # Write in binary mode for performance
            cache_file.write_bytes(json_content.encode('utf-8'))
            return True
        except Exception as e:
            logging.warning(f"⚠️ Direct save failed: {e}")
            return False
    
    def clear_cache(self, cache_file: Path) -> bool:
        """Clear cache file with error handling."""
        try:
            if cache_file.exists():
                cache_file.unlink()
            return True
        except OSError as e:
            logging.warning(f"⚠️ Clear cache failed: {e}")
            return False