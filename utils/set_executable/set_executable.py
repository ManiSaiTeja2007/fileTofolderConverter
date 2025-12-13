from pathlib import Path
import stat
import logging
import os
from typing import Union, List

def set_executable(path: Union[Path, str]) -> bool:
    """
    Set executable permissions on a file with comprehensive validation.
    
    Args:
        path: Path to the file to make executable
        
    Returns:
        True if successful, False otherwise
    """
    # Convert string to Path if needed
    if isinstance(path, str):
        path = Path(path)
    
    # Input validation
    if not isinstance(path, Path):
        logging.warning(f"⚠️ Invalid path type: {type(path)}")
        return False
    
    try:
        # Check if file exists
        if not path.exists():
            logging.warning(f"⚠️ File not found: {path}")
            return False
        
        # Check if it's actually a file
        if not path.is_file():
            logging.warning(f"⚠️ Path is not a file: {path}")
            return False
        
        # Check current permissions
        current_mode = path.stat().st_mode
        
        # Check if already executable
        if current_mode & stat.S_IEXEC:
            logging.debug(f"ℹ️ File already executable: {path}")
            return True
        
        # Set executable permissions for user, group, and others
        new_mode = current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        path.chmod(new_mode)
        
        # Verify the change
        verified_mode = path.stat().st_mode
        if verified_mode & stat.S_IEXEC:
            logging.debug(f"✅ Set executable permissions: {path}")
            return True
        else:
            logging.warning(f"⚠️ Failed to verify executable permissions: {path}")
            return False
            
    except PermissionError:
        logging.warning(f"❌ Permission denied setting executable on {path}")
        return False
    except OSError as e:
        logging.warning(f"❌ OS error setting executable on {path}: {e}")
        return False
    except Exception as e:
        logging.warning(f"❌ Unexpected error setting executable on {path}: {e}")
        return False

def set_executable_by_pattern(directory: Path, patterns: List[str]) -> int:
    """
    Set executable permissions on multiple files matching patterns.
    
    Args:
        directory: Directory to search in
        patterns: List of filename patterns to match (e.g., ["*.sh", "*.py"])
        
    Returns:
        Number of files successfully made executable
    """
    if not directory.is_dir():
        logging.warning(f"⚠️ Directory not found: {directory}")
        return 0
    
    success_count = 0
    
    try:
        for pattern in patterns:
            for file_path in directory.rglob(pattern):
                if set_executable(file_path):
                    success_count += 1
                    
        logging.info(f"✅ Made {success_count} files executable in {directory}")
        return success_count
        
    except Exception as e:
        logging.warning(f"⚠️ Error processing executable patterns in {directory}: {e}")
        return success_count

def set_executable_by_name(directory: Path, filenames: List[str]) -> int:
    """
    Set executable permissions on specific filenames.
    
    Args:
        directory: Directory to search in
        filenames: List of exact filenames to make executable
        
    Returns:
        Number of files successfully made executable
    """
    if not directory.is_dir():
        logging.warning(f"⚠️ Directory not found: {directory}")
        return 0
    
    success_count = 0
    
    try:
        for filename in filenames:
            for file_path in directory.rglob(filename):
                if file_path.name == filename and set_executable(file_path):
                    success_count += 1
                    
        logging.info(f"✅ Made {success_count} named files executable in {directory}")
        return success_count
        
    except Exception as e:
        logging.warning(f"⚠️ Error processing named executables in {directory}: {e}")
        return success_count

def is_executable(path: Path) -> bool:
    """
    Check if a file has executable permissions.
    
    Args:
        path: Path to check
        
    Returns:
        True if file is executable
    """
    try:
        if not path.exists() or not path.is_file():
            return False
        
        mode = path.stat().st_mode
        return bool(mode & stat.S_IEXEC)
        
    except Exception as e:
        logging.debug(f"⚠️ Error checking executable status of {path}: {e}")
        return False

def remove_executable(path: Path) -> bool:
    """
    Remove executable permissions from a file.
    
    Args:
        path: Path to the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not path.exists():
            logging.warning(f"⚠️ File not found: {path}")
            return False
        
        current_mode = path.stat().st_mode
        new_mode = current_mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        path.chmod(new_mode)
        
        logging.debug(f"✅ Removed executable permissions: {path}")
        return True
        
    except Exception as e:
        logging.warning(f"⚠️ Failed to remove executable permissions from {path}: {e}")
        return False

# Common executable file patterns
DEFAULT_EXECUTABLE_PATTERNS = ["*.sh", "*.bash", "*.zsh", "*.py", "*.pl", "*.rb"]
DEFAULT_EXECUTABLE_NAMES = ["Makefile", "Procfile", "gradlew", "mvnw"]

def set_default_executables(directory: Path) -> int:
    """
    Set executable permissions on common executable files.
    
    Args:
        directory: Directory to process
        
    Returns:
        Number of files made executable
    """
    count_patterns = set_executable_by_pattern(directory, DEFAULT_EXECUTABLE_PATTERNS)
    count_names = set_executable_by_name(directory, DEFAULT_EXECUTABLE_NAMES)
    
    total = count_patterns + count_names
    logging.info(f"✅ Set executable permissions on {total} default files in {directory}")
    return total

def get_executable_files(directory: Path) -> List[Path]:
    """
    Get list of executable files in a directory.
    
    Args:
        directory: Directory to search
        
    Returns:
        List of executable file paths
    """
    executable_files = []
    
    try:
        for file_path in directory.rglob("*"):
            if file_path.is_file() and is_executable(file_path):
                executable_files.append(file_path)
                
        return executable_files
        
    except Exception as e:
        logging.warning(f"⚠️ Error scanning for executable files in {directory}: {e}")
        return []