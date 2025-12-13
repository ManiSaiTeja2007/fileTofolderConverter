"""
High-performance caching system with modular components.
"""

from .cache import CacheManager
from .utils import generate_cache_key, get_cache_info, debug_cache_operations

__version__ = "1.0.0"
__all__ = ['CacheManager', 'generate_cache_key', 'get_cache_info', 'debug_cache_operations']