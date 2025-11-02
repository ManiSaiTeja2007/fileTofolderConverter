from pathlib import Path
import json
import logging
from typing import Dict, Optional, Union, List
from functools import lru_cache
import os

# Import all components
from .comment_placeholders import EXT_COMMENT_PLACEHOLDER, get_default_placeholder
from .special_files import SPECIAL_FILES, is_special_file
from .comment_prefixes import get_comment_prefix, get_comment_suffix
from .config_loader import load_config_file, find_config_candidates, merge_placeholders_from_file, debug_config_loading

# Re-export everything for backward compatibility
__all__ = [
    'EXT_COMMENT_PLACEHOLDER',
    'SPECIAL_FILES', 
    'get_comment_prefix',
    'get_comment_suffix',
    'get_default_placeholder',
    'load_config_file',
    'find_config_candidates',
    'merge_placeholders_from_file',
    'is_special_file',
    'debug_config_loading'
]