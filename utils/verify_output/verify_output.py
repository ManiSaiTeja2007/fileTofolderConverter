from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
import logging
import os

from utils.is_probably_file.is_probably_file import is_probably_file
from utils.normalize_path_segment.normalize_path_segment import normalize_path_segment

def verify_output(
    out_root: Path,
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    warnings: List[str],
    files_always: Optional[Set[str]] = None,
    dirs_always: Optional[Set[str]] = None,
    excluded_files: Optional[Set[str]] = None
) -> Dict[str, any]:
    """
    Verify generated output against expected structure with comprehensive checks.
    """
    # Input validation
    if not isinstance(out_root, Path):
        warnings.append("❌ Output root must be a Path object")
        return {}
    
    if not out_root.exists():
        warnings.append("❌ Output directory does not exist")
        return {}
    
    if not out_root.is_dir():
        warnings.append("❌ Output path is not a directory")
        return {}
    
    stats = {
        "total_files_expected": 0,
        "files_found": 0,
        "files_missing": 0,
        "files_empty": 0,
        "files_with_multiple_blocks": 0,
        "files_with_content_mismatch": 0,
        "unexpected_files_found": 0,
        "directories_expected": 0,
        "directories_found": 0,
        "directories_missing": 0,
        "excluded_files_count": 0,
        "verification_passed": False
    }
    
    files_always = files_always or set()
    dirs_always = dirs_always or set()
    excluded_files = excluded_files or set()
    
    # Add default exclusions
    default_exclusions = {'.git', '.git/**', 'node_modules', 'node_modules/**'}
    all_excluded_files = excluded_files | default_exclusions
    
    logging.info(f"🔍 Verifying output in {out_root} ({len(tree_entries)} expected entries)")
    
    # Clean tree entries by removing ASCII tree characters
    cleaned_tree_entries = clean_tree_entries(tree_entries)
    
    # Separate files from directories in the cleaned tree entries
    expected_files = {}  # cleaned_path -> original_path
    expected_dirs = set()
    
    for original_entry, cleaned_entry in cleaned_tree_entries:
        try:
            if not cleaned_entry:
                continue
                
            # Check if this path is excluded
            if is_path_excluded(cleaned_entry, all_excluded_files):
                stats["excluded_files_count"] += 1
                logging.debug(f"⏭️  Excluded from verification: {cleaned_entry}")
                continue
                
            name = Path(cleaned_entry).name
            
            if is_probably_file(name, files_always, dirs_always):
                expected_files[cleaned_entry] = original_entry
                stats["total_files_expected"] += 1
            else:
                expected_dirs.add(cleaned_entry)
                stats["directories_expected"] += 1
                
        except Exception as e:
            warnings.append(f"⚠️ Error processing tree entry '{original_entry}': {e}")
            continue
    
        # Verify expected files
    for cleaned_path, original_path in expected_files.items():
        try:
            # Normalize the path to avoid slash or case issues
            cleaned_path = os.path.normpath(cleaned_path).lstrip('./')
            fs_path = out_root / cleaned_path
            
            logging.debug(f"Checking file existence: {fs_path}")
            
            # Check file existence
            if not fs_path.exists():
                warnings.append(f"❌ Missing file: {cleaned_path}")
                stats["files_missing"] += 1
                continue
            
            # Check if it's actually a file (and not a directory or symlink)
            if not fs_path.is_file():
                warnings.append(f"❌ Path exists but is not a file: {cleaned_path}")
                continue
            
            stats["files_found"] += 1
            
            # Check file content
            code_map_key = find_code_map_key(cleaned_path, original_path, code_map)
            file_issues = verify_file_content(fs_path, cleaned_path, code_map_key, code_map, warnings)
            stats["files_empty"] += file_issues["empty"]
            stats["files_with_multiple_blocks"] += file_issues["multiple_blocks"]
            stats["files_with_content_mismatch"] += file_issues["content_mismatch"]
            
        except Exception as e:
            warnings.append(f"❌ Error verifying file {cleaned_path}: {e}")
            continue
    
    # Verify expected directories
    for dir_entry in expected_dirs:
        try:
            path = out_root / dir_entry
            
            if not path.exists():
                warnings.append(f"❌ Missing directory: {dir_entry}")
                stats["directories_missing"] += 1
                continue
            
            stats["directories_found"] += 1
            
            if not path.is_dir():
                warnings.append(f"❌ Path exists but is not a directory: {dir_entry}")
                
        except Exception as e:
            warnings.append(f"❌ Error verifying directory {dir_entry}: {e}")
            continue
    
    # Check for unexpected files (excluding the excluded ones)
    if expected_files or expected_dirs:
        unexpected_count = check_unexpected_files(
            out_root, 
            set(expected_files.keys()) | expected_dirs, 
            all_excluded_files,
            warnings
        )
        stats["unexpected_files_found"] = unexpected_count
    
    # Determine overall verification status
    files_to_verify = stats["total_files_expected"] - stats["excluded_files_count"]
    stats["verification_passed"] = (
        stats["files_missing"] == 0 and 
        stats["directories_missing"] == 0 and
        stats["unexpected_files_found"] == 0 and
        (files_to_verify == 0 or stats["files_found"] > 0)
    )
    
    # Log summary
    log_verification_summary(stats, warnings)
    
    return stats

def clean_tree_entries(tree_entries: List[str]) -> List[Tuple[str, str]]:
    """
    Clean ASCII tree characters from tree entries and reconstruct proper paths.
    Returns list of tuples (original_entry, cleaned_entry)
    """
    cleaned_entries = []
    path_stack = []  # Stack to track current directory path
    
    for entry in tree_entries:
        # Calculate indent level by counting tree characters
        indent_chars = 0
        for char in ['│', '├', '└']:
            indent_chars += entry.count(char)
        
        # Remove all tree characters and clean up
        clean_line = entry
        for char in ['│', '├', '└', '──', '─']:
            clean_line = clean_line.replace(char, ' ')
        
        # Clean up whitespace and get the name
        clean_line = ' '.join(clean_line.split()).strip()
        
        if not clean_line:
            continue
            
        # Remove trailing slash if present (directory indicator)
        is_directory = clean_line.endswith('/')
        name = clean_line.rstrip('/')
        
        # Update path stack based on indent level
        # Each '├' or '└' represents one level of indentation
        indent_level = max(0, indent_chars - 1)  # Adjust for root level
        
        # Trim stack to current indent level
        path_stack = path_stack[:indent_level]
        
        if is_directory:
            # It's a directory - add to path stack
            path_stack.append(name)
            cleaned_path = '/'.join(path_stack)
            cleaned_entries.append((entry, cleaned_path))
        else:
            # It's a file - use current path stack + filename
            if path_stack:
                cleaned_path = '/'.join(path_stack + [name])
            else:
                cleaned_path = name
            cleaned_entries.append((entry, cleaned_path))
    
    return cleaned_entries    
def is_path_excluded(path: str, excluded_patterns: Set[str]) -> bool:
    """
    Check if a path matches any exclusion pattern.
    Supports glob patterns with ** for recursive matching.
    """
    from fnmatch import fnmatch
    
    for pattern in excluded_patterns:
        if fnmatch(path, pattern):
            return True
        # Also check if this is a parent of an excluded pattern
        if '**' in pattern:
            base_pattern = pattern.replace('/**', '')
            if path.startswith(base_pattern):
                return True
    return False

def find_code_map_key(cleaned_path: str, original_path: str, code_map: Dict[str, List[str]]) -> Optional[str]:
    """
    Find the correct key in code_map for a given file path.
    """
    # Try cleaned path first
    if cleaned_path in code_map:
        return cleaned_path
    
    # Try original path (with tree characters removed)
    if original_path in code_map:
        return original_path
    
    # Try to clean the original path more aggressively
    aggressive_clean = ' '.join(original_path.replace('│', '').replace('├', '').replace('└', '').replace('──', '').split()).strip()
    if aggressive_clean in code_map:
        return aggressive_clean
    
    # Try various normalizations
    variations = [
        cleaned_path,
        original_path,
        aggressive_clean,
        cleaned_path.lstrip('./'),
        original_path.lstrip('./'),
    ]
    
    for variation in variations:
        if variation in code_map:
            return variation
    
    # Try to find by filename only (last resort)
    filename = Path(cleaned_path).name
    for key in code_map.keys():
        if Path(key).name == filename:
            return key
    
    return None

def verify_file_content(
    path: Path,
    display_path: str,
    code_map_key: Optional[str],
    code_map: Dict[str, List[str]],
    warnings: List[str]
) -> Dict[str, int]:
    """
    Verify individual file content and properties.
    """
    issues = {
        "empty": 0,
        "multiple_blocks": 0,
        "content_mismatch": 0
    }
    
    try:
        # Check file size
        file_size = path.stat().st_size
        if file_size == 0:
            warnings.append(f"⚠️ Empty file: {display_path}")
            issues["empty"] = 1
        
        # Check for multiple code blocks
        if code_map_key and code_map_key in code_map:
            assigned_blocks = code_map[code_map_key]
            if len(assigned_blocks) > 1:
                warnings.append(f"⚠️ File {display_path} had {len(assigned_blocks)} code blocks merged")
                issues["multiple_blocks"] = 1
            
            # Verify content matches expected
            if assigned_blocks and file_size > 0:
                content_match = verify_content_match(path, assigned_blocks, warnings)
                if not content_match:
                    issues["content_mismatch"] = 1
        else:
            logging.debug(f"ℹ️ No code blocks assigned to: {display_path}")
        
    except PermissionError:
        warnings.append(f"❌ Permission denied accessing: {display_path}")
    except Exception as e:
        warnings.append(f"❌ Error checking file {display_path}: {e}")
    
    return issues

def verify_content_match(
    path: Path, 
    expected_blocks: List[str], 
    warnings: List[str]
) -> bool:
    """
    Verify file content matches expected code blocks.
    """
    try:
        actual_content = path.read_text(encoding='utf-8', errors='replace').strip()
        expected_content = "\n\n".join(expected_blocks).strip()
        
        if actual_content != expected_content:
            if actual_content.replace('\r\n', '\n') != expected_content.replace('\r\n', '\n'):
                warnings.append(f"⚠️ Content mismatch in {path.name}")
                return False
        
        return True
        
    except Exception as e:
        warnings.append(f"⚠️ Could not verify content for {path}: {e}")
        return False

def check_unexpected_files(
    out_root: Path,
    all_expected_paths: Set[str],
    excluded_patterns: Set[str],
    warnings: List[str]
) -> int:
    """
    Check for files that were generated but not in the original tree.
    """
    unexpected_count = 0
    
    try:
        # Walk through generated output
        for item_path in out_root.rglob('*'):
            if not item_path.is_file():
                continue
            
            # Get relative path from output root
            try:
                rel_path = item_path.relative_to(out_root)
                rel_path_str = str(rel_path).replace('\\', '/')
            except ValueError:
                continue
            
            # Skip excluded files using pattern matching
            if is_path_excluded(rel_path_str, excluded_patterns):
                continue
            
            # Skip common generated files
            if rel_path_str in {'report.md', 'README.md'}:
                continue
            if rel_path_str.startswith('UNASSIGNED/'):
                continue
            
            # Check if this file was expected
            if rel_path_str not in all_expected_paths:
                # Also check if any expected path starts with this path
                is_nested_expected = any(
                    rel_path_str.startswith(expected + '/') 
                    for expected in all_expected_paths
                )
                
                if not is_nested_expected:
                    warnings.append(f"⚠️ Unexpected file generated: {rel_path_str}")
                    unexpected_count += 1
    
    except Exception as e:
        warnings.append(f"❌ Error checking for unexpected files: {e}")
    
    return unexpected_count

def log_verification_summary(stats: Dict[str, any], warnings: List[str]) -> None:
    """
    Log verification summary.
    """
    if stats["verification_passed"]:
        logging.info("✅ Output verification PASSED")
    else:
        logging.warning("⚠️ Output verification found issues")
    
    logging.info(f"📊 Verification Summary:")
    logging.info(f"   Expected files: {stats['total_files_expected']}")
    logging.info(f"   Excluded files: {stats['excluded_files_count']}")
    logging.info(f"   Files to verify: {stats['total_files_expected'] - stats['excluded_files_count']}")
    logging.info(f"   Found files: {stats['files_found']}")
    logging.info(f"   Missing files: {stats['files_missing']}")
    logging.info(f"   Empty files: {stats['files_empty']}")
    logging.info(f"   Expected directories: {stats['directories_expected']}")
    logging.info(f"   Found directories: {stats['directories_found']}")
    logging.info(f"   Missing directories: {stats['directories_missing']}")
    logging.info(f"   Unexpected files: {stats['unexpected_files_found']}")
    logging.info(f"   Total warnings: {len(warnings)}")