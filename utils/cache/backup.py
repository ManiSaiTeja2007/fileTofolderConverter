"""
Backup and restore operations for cache files.
"""
import logging
from pathlib import Path
import shutil


def create_backup(cache_file: Path, backup_suffix: str = '.bak') -> bool:
    """
    Create backup of cache file.
    
    Args:
        cache_file: Cache file to backup
        backup_suffix: Backup file suffix
        
    Returns:
        Success status
    """
    try:
        backup_file = cache_file.with_suffix(cache_file.suffix + backup_suffix)
        
        # Use copy2 to preserve metadata
        shutil.copy2(cache_file, backup_file)
        logging.debug(f"✅ Created cache backup: {backup_file}")
        return True
        
    except Exception as e:
        logging.warning(f"⚠️ Backup creation failed: {e}")
        return False


def restore_backup(cache_file: Path, backup_suffix: str = '.bak') -> bool:
    """
    Restore cache from backup.
    
    Args:
        cache_file: Cache file to restore
        backup_suffix: Backup file suffix
        
    Returns:
        Success status
    """
    try:
        backup_file = cache_file.with_suffix(cache_file.suffix + backup_suffix)
        
        if backup_file.exists():
            shutil.copy2(backup_file, cache_file)
            logging.debug(f"✅ Restored cache from backup: {backup_file}")
            return True
        return False
        
    except Exception as e:
        logging.warning(f"⚠️ Backup restoration failed: {e}")
        return False


def cleanup_old_backups(cache_file: Path, backup_suffix: str = '.bak', 
                       keep_count: int = 3) -> bool:
    """
    Cleanup old backup files, keeping only the most recent ones.
    
    Args:
        cache_file: Base cache file path
        backup_suffix: Backup file suffix
        keep_count: Number of recent backups to keep
        
    Returns:
        Success status
    """
    try:
        backup_pattern = f"*{cache_file.suffix}{backup_suffix}"
        backups = sorted(cache_file.parent.glob(backup_pattern), 
                        key=lambda x: x.stat().st_mtime, 
                        reverse=True)
        
        # Remove old backups beyond keep_count
        for backup in backups[keep_count:]:
            backup.unlink()
            logging.debug(f"✅ Cleaned up old backup: {backup}")
        
        return True
        
    except Exception as e:
        logging.warning(f"⚠️ Backup cleanup failed: {e}")
        return False