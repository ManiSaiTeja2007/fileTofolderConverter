from pathlib import Path
from typing import List, Optional
import logging
import os

def safe_write_text(
    path: Path, 
    content: str, 
    warnings: List[str], 
    no_overwrite: bool = False,
    create_backup: bool = False,
    max_file_size: int = 100 * 1024 * 1024  # 100MB default limit
) -> bool:
    """
    Write text safely with comprehensive validation and error handling.
    
    Args:
        path: Target file path
        content: Content to write
        warnings: List to append warning messages to
        no_overwrite: If True, don't overwrite existing files
        create_backup: If True, create backup of existing file
        max_file_size: Maximum allowed file size in bytes
        
    Returns:
        True if file was written successfully, False otherwise
    """
    # Input validation
    if not isinstance(path, Path):
        warnings.append(f"❌ Invalid path type: {type(path)}")
        return False
    
    if not isinstance(content, str):
        warnings.append(f"❌ Content must be string, got {type(content)}")
        return False
    
    if warnings is None:
        warnings = []
    
    try:
        # Check content size before writing
        content_size = len(content.encode('utf-8'))
        if content_size > max_file_size:
            warnings.append(f"❌ Content too large: {content_size} bytes > {max_file_size} bytes limit")
            return False
        
        # Create parent directories
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            warnings.append(f"❌ Permission denied creating directories for {path}")
            return False
        except Exception as e:
            warnings.append(f"❌ Failed to create parent directories for {path}: {e}")
            return False
        
        # Check existing path conflicts
        if path.exists():
            if path.is_dir():
                warnings.append(f"❌ Path exists as directory: {path}")
                return False
            
            if no_overwrite:
                warnings.append(f"ℹ️ Skipped existing file (--no-overwrite): {path}")
                return False
            
            # Check if we can actually write to the file
            if not os.access(path, os.W_OK):
                warnings.append(f"❌ No write permission for existing file: {path}")
                return False
            
            # Create backup if requested
            if create_backup:
                backup_path = path.with_suffix(path.suffix + '.bak')
                try:
                    path.rename(backup_path)
                    logging.debug(f"✅ Created backup: {backup_path}")
                except Exception as e:
                    warnings.append(f"⚠️ Failed to create backup for {path}: {e}")
        
        # Validate parent structure
        if path.parent.exists() and path.parent.is_file():
            warnings.append(f"❌ Invalid structure: Parent is a file: {path.parent}")
            return False
        
        # Check parent directory write permissions
        if not os.access(path.parent, os.W_OK):
            warnings.append(f"❌ No write permission for directory: {path.parent}")
            return False
        
        # Write file with atomic operation
        temp_path = path.with_suffix(path.suffix + '.tmp')
        
        try:
            # Write to temporary file first
            with open(temp_path, 'w', encoding='utf-8', errors='strict') as f:
                f.write(content)
            
            # Verify the temporary file was written correctly
            if not temp_path.exists():
                warnings.append(f"❌ Temporary file was not created: {temp_path}")
                return False
            
            temp_size = temp_path.stat().st_size
            if temp_size == 0 and content:
                warnings.append(f"❌ Temporary file is empty but content was provided: {temp_path}")
                temp_path.unlink(missing_ok=True)
                return False
            
            # Atomic replace
            temp_path.replace(path)
            logging.debug(f"✅ Successfully wrote: {path} ({len(content)} characters)")
            return True
            
        except UnicodeEncodeError as e:
            warnings.append(f"❌ Encoding error writing {path}: {e}")
            temp_path.unlink(missing_ok=True)
            return False
        except Exception as e:
            warnings.append(f"❌ Error during file write operation for {path}: {e}")
            temp_path.unlink(missing_ok=True)
            return False
        
    except Exception as e:
        warnings.append(f"❌ Unexpected error writing {path}: {e}")
        return False

def safe_read_text(path: Path, warnings: List[str]) -> Optional[str]:
    """
    Safely read text from a file with error handling.
    
    Args:
        path: File path to read
        warnings: List to append warning messages to
        
    Returns:
        File content as string, or None if failed
    """
    if not path.exists():
        warnings.append(f"❌ File not found: {path}")
        return None
    
    if path.is_dir():
        warnings.append(f"❌ Path is a directory, not a file: {path}")
        return None
    
    try:
        # Check file size before reading
        file_size = path.stat().st_size
        max_size = 100 * 1024 * 1024  # 100MB limit
        
        if file_size > max_size:
            warnings.append(f"❌ File too large to read: {file_size} bytes > {max_size} bytes")
            return None
        
        # Check read permissions
        if not os.access(path, os.R_OK):
            warnings.append(f"❌ No read permission for file: {path}")
            return None
        
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        logging.debug(f"✅ Successfully read: {path} ({len(content)} characters)")
        return content
        
    except UnicodeDecodeError as e:
        warnings.append(f"❌ Encoding error reading {path}: {e}")
        return None
    except PermissionError:
        warnings.append(f"❌ Permission denied reading {path}")
        return None
    except Exception as e:
        warnings.append(f"❌ Error reading {path}: {e}")
        return None

def safe_copy_file(source: Path, target: Path, warnings: List[str], no_overwrite: bool = False) -> bool:
    """
    Safely copy a file with comprehensive error handling.
    
    Args:
        source: Source file path
        target: Target file path
        warnings: List to append warning messages to
        no_overwrite: If True, don't overwrite existing files
        
    Returns:
        True if copy was successful, False otherwise
    """
    # Validate source
    if not source.exists():
        warnings.append(f"❌ Source file not found: {source}")
        return False
    
    if source.is_dir():
        warnings.append(f"❌ Source is a directory: {source}")
        return False
    
    # Use safe_write_text to handle the target side
    content = safe_read_text(source, warnings)
    if content is None:
        return False
    
    return safe_write_text(target, content, warnings, no_overwrite=no_overwrite)