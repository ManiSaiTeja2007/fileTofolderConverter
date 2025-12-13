from pathlib import Path
from typing import Dict, Optional, Union
import logging

from utils.compute_hash.compute_hash import compute_hash

def should_update(
    path: Path, 
    content: str, 
    cache: Dict, 
    force_update: bool = False,
    check_existence: bool = True
) -> bool:
    """
    Determine if a file should be updated based on content changes and cache.
    
    Args:
        path: File path to check
        content: New content to compare
        cache: Cache dictionary storing file hashes
        force_update: If True, always return True (force update)
        check_existence: If True, also check if file exists and matches
        
    Returns:
        True if file should be updated, False otherwise
    """
    # Input validation
    if not isinstance(path, Path):
        logging.warning(f"⚠️ Invalid path type: {type(path)}")
        return True
    
    if not isinstance(content, str):
        logging.warning(f"⚠️ Content must be string, got {type(content)}")
        return True
    
    if cache is None:
        logging.warning("⚠️ Cache is None, forcing update")
        return True
    
    # Force update takes precedence
    if force_update:
        logging.debug(f"🔨 Force update requested for: {path}")
        return True
    
    try:
        # Compute hash of new content
        new_hash = compute_hash(content)
        if not new_hash:
            logging.warning(f"⚠️ Failed to compute hash for {path}, forcing update")
            return True
        
        # Check cache for previous hash
        cache_key = str(path)
        old_hash = cache.get(cache_key)
        
        # If no cache entry, file should be updated
        if old_hash is None:
            logging.debug(f"📝 No cache entry for {path}, will update")
            return True
        
        # Compare hashes
        if new_hash != old_hash:
            logging.debug(f"📝 Content changed for {path}, will update")
            return True
        
        # Additional existence check if requested
        if check_existence:
            if not path.exists():
                logging.debug(f"📝 File missing {path}, will update")
                return True
            
            # Verify existing file content matches cache
            try:
                existing_content = path.read_text(encoding='utf-8')
                existing_hash = compute_hash(existing_content)
                if existing_hash != old_hash:
                    logging.debug(f"📝 File content mismatch for {path}, will update")
                    return True
            except Exception as e:
                logging.debug(f"⚠️ Error reading existing file {path}: {e}, will update")
                return True
        
        logging.debug(f"✅ File unchanged: {path}, skipping update")
        return False
        
    except Exception as e:
        logging.warning(f"⚠️ Error in update check for {path}: {e}, forcing update")
        return True

def update_cache(path: Path, content: str, cache: Dict) -> bool:
    """
    Update cache with current file hash.
    
    Args:
        path: File path to update in cache
        content: Current file content
        cache: Cache dictionary to update
        
    Returns:
        True if cache was updated successfully
    """
    try:
        cache_key = str(path)
        new_hash = compute_hash(content)
        
        if new_hash:
            cache[cache_key] = new_hash
            logging.debug(f"💾 Updated cache for: {path}")
            return True
        else:
            logging.warning(f"⚠️ Failed to compute hash for cache update: {path}")
            return False
            
    except Exception as e:
        logging.warning(f"⚠️ Failed to update cache for {path}: {e}")
        return False

def batch_should_update(
    files: Dict[Path, str], 
    cache: Dict,
    force_update: bool = False
) -> Dict[Path, bool]:
    """
    Batch check multiple files for updates.
    
    Args:
        files: Dictionary mapping paths to content
        cache: Cache dictionary
        force_update: If True, all files will be updated
        
    Returns:
        Dictionary mapping paths to update decisions
    """
    update_decisions = {}
    
    for path, content in files.items():
        try:
            should_update_file = should_update(
                path, content, cache, 
                force_update=force_update
            )
            update_decisions[path] = should_update_file
            
            if should_update_file:
                logging.debug(f"📝 Queued for update: {path}")
                
        except Exception as e:
            logging.warning(f"⚠️ Error processing {path}: {e}")
            update_decisions[path] = True  # Update on error
    
    logging.info(f"📊 Batch update analysis: {sum(update_decisions.values())}/{len(files)} files need updates")
    return update_decisions

def get_files_needing_update(
    files: Dict[Path, str], 
    cache: Dict
) -> Dict[Path, str]:
    """
    Get only the files that need updates.
    
    Args:
        files: Dictionary mapping paths to content
        cache: Cache dictionary
        
    Returns:
        Dictionary of files that need updates
    """
    update_decisions = batch_should_update(files, cache)
    return {
        path: content 
        for path, content in files.items() 
        if update_decisions.get(path, True)
    }

def validate_cache_consistency(files: Dict[Path, str], cache: Dict) -> Dict[Path, str]:
    """
    Validate cache consistency and return inconsistencies.
    
    Args:
        files: Dictionary mapping paths to content
        cache: Cache dictionary to validate
        
    Returns:
        Dictionary of files with cache inconsistencies
    """
    inconsistencies = {}
    
    for path, content in files.items():
        cache_key = str(path)
        cached_hash = cache.get(cache_key)
        
        if cached_hash is not None:
            current_hash = compute_hash(content)
            if current_hash and current_hash != cached_hash:
                inconsistencies[path] = content
                logging.debug(f"🔍 Cache inconsistency detected: {path}")
    
    if inconsistencies:
        logging.warning(f"⚠️ Found {len(inconsistencies)} cache inconsistencies")
    
    return inconsistencies

def cleanup_stale_cache_entries(cache: Dict, existing_files: list[Path]) -> int:
    """
    Remove stale cache entries for files that no longer exist.
    
    Args:
        cache: Cache dictionary to clean up
        existing_files: List of currently existing files
        
    Returns:
        Number of entries removed
    """
    existing_paths = {str(path) for path in existing_files}
    stale_entries = [key for key in cache.keys() if key not in existing_paths]
    
    for stale_key in stale_entries:
        del cache[stale_key]
    
    if stale_entries:
        logging.info(f"🧹 Cleaned up {len(stale_entries)} stale cache entries")
    
    return len(stale_entries)