from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional, Any
import logging
from fnmatch import fnmatch

from utils.safe_write_text.safe_write_text import safe_write_text
from utils.validate_entry_path.validate_entry_path import validate_entry_path
from utils.normalize_path_segment.normalize_path_segment import normalize_path_segment
from utils.is_probably_file.is_probably_file import is_probably_file
from utils.config.config import EXT_COMMENT_PLACEHOLDER, get_comment_prefix

def should_ignore_entry(entry: str, ignore_patterns: List[str]) -> bool:
    """
    Check if an entry should be ignored based on patterns.
    
    Args:
        entry: Entry path to check
        ignore_patterns: List of glob patterns to ignore
        
    Returns:
        True if entry should be ignored
    """
    if not ignore_patterns:
        return False
    
    return any(fnmatch(entry, pat) for pat in ignore_patterns)

def prepare_file_content(
    entry: str,
    code_map: Dict[str, List[str]],
    heading_map: Dict[str, str],
    skip_empty: bool
) -> Tuple[Optional[str], bool, Optional[str]]:
    """
    Prepare content for a file, handling placeholders and headings.
    
    Args:
        entry: File entry path
        code_map: Mapping of entries to code blocks
        heading_map: Mapping of entries to headings
        skip_empty: Whether to skip empty files
        
    Returns:
        Tuple of (content, is_placeholder, warning_message)
    """
    content_parts = code_map.get(entry, [])
    
    # Handle files with actual content
    if content_parts:
        content = "\n\n".join(content_parts).strip()
        if content:  # Ensure we don't write completely empty files
            content += "\n"
            return content, False, None
        else:
            return None, False, f"File '{entry}' has empty content blocks"
    
    # Handle placeholder files
    if skip_empty:
        return None, True, f"ℹ️ Skipped placeholder file {entry} due to --skip-empty"
    
    # Create placeholder content
    name = Path(entry).name
    ext = "." + name.split(".")[-1] if "." in name else ""
    content = EXT_COMMENT_PLACEHOLDER.get(ext, EXT_COMMENT_PLACEHOLDER["default"])
    
    return content, True, None

def add_heading_comment(content: str, entry: str, heading_map: Dict[str, str]) -> str:
    """
    Add heading as a comment to the file content.
    
    Args:
        content: Original file content
        entry: File entry path
        heading_map: Mapping of entries to headings
        
    Returns:
        Content with heading comment prepended
    """
    if entry not in heading_map:
        return content
    
    heading = heading_map[entry]
    ext = Path(entry).suffix.lower()
    prefix = get_comment_prefix(ext)
    
    if not prefix:
        return content
    
    # Format the heading comment based on comment style
    if prefix == "/* ":
        heading_comment = f"/* {heading} */\n"
    elif prefix == "<!-- ":
        heading_comment = f"<!-- {heading} -->\n"
    else:
        heading_comment = f"{prefix}{heading}\n"
    
    return heading_comment + content

def count_content_lines(content: str) -> int:
    """
    Count the number of lines in content.
    
    Args:
        content: Text content to count
        
    Returns:
        Number of lines
    """
    if not content:
        return 0
    return content.count("\n") + (1 if content and not content.endswith("\n") else 0)

def process_file_entry(
    entry: str,
    out_root: Path,
    code_map: Dict[str, List[str]],
    heading_map: Dict[str, str],
    dry_run: bool,
    verbose: bool,
    skip_empty: bool,
    no_overwrite: bool,
    files_always: Set,
    dirs_always: Set,
    warnings: List[str]
) -> Tuple[Optional[str], int, int, int]:
    """
    Process a single file entry for writing.
    
    Args:
        entry: File entry path
        out_root: Root output directory
        code_map: Code blocks mapping
        heading_map: Headings mapping
        dry_run: Whether to simulate writing
        verbose: Whether to log verbose output
        skip_empty: Whether to skip empty files
        no_overwrite: Whether to prevent overwriting
        files_always: Files always set
        dirs_always: Directories always set
        warnings: Warnings list to append to
        
    Returns:
        Tuple of (file_path, lines_written, placeholder_flag, files_written_flag)
    """
    # Validate entry
    err = validate_entry_path(entry)
    if err:
        warnings.append(f"❌ Unsafe path '{entry}': {err}")
        return None, 0, 0, 0
    
    # Prepare content
    content, is_placeholder, content_warning = prepare_file_content(
        entry, code_map, heading_map, skip_empty
    )
    
    if content_warning:
        warnings.append(content_warning)
    
    if content is None:
        return None, 0, int(is_placeholder), 0
    
    # Add heading comment if available
    content_with_heading = add_heading_comment(content, entry, heading_map)
    
    # Create file path
    parts = entry.split("/")
    file_path = out_root.joinpath(*parts)
    
    # Log verbose output
    if verbose:
        log_msg = f"[write] {file_path}"
        if is_placeholder:
            log_msg += " (placeholder)"
        logging.debug(log_msg)
    
    # Write file (or simulate)
    lines_written = count_content_lines(content_with_heading)
    files_written = 0
    
    if not dry_run:
        written = safe_write_text(file_path, content_with_heading, warnings, no_overwrite=no_overwrite)
        if written:
            files_written = 1
    
    return str(file_path), lines_written, int(is_placeholder), files_written

def process_directory_entry(
    entry: str,
    out_root: Path,
    dry_run: bool,
    warnings: List[str]
) -> Optional[str]:
    """
    Process a single directory entry for creation.
    
    Args:
        entry: Directory entry path
        out_root: Root output directory
        dry_run: Whether to simulate creation
        warnings: Warnings list to append to
        
    Returns:
        Directory path if created, None otherwise
    """
    # Validate entry
    err = validate_entry_path(entry)
    if err:
        warnings.append(f"❌ Unsafe path '{entry}': {err}")
        return None
    
    # Create directory path
    parts = entry.split("/")
    dir_path = out_root.joinpath(*parts)
    
    # Create directory
    if not dry_run:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            logging.debug(f"📁 Created directory: {dir_path}")
        except Exception as e:
            warnings.append(f"⚠️ Failed to create directory {dir_path}: {e}")
            return None
    
    return str(dir_path)

def reconcile_and_write(
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    out_root: Path,
    dry_run: bool = False,
    verbose: bool = False,
    skip_empty: bool = False,
    ignore_patterns: Optional[List[str]] = None,
    files_always: Optional[Set] = None,
    dirs_always: Optional[Set] = None,
    no_overwrite: bool = False,
    heading_map: Dict[str, str] = {},
) -> Tuple[Set, List[str], List[str], int, int, int]:
    """
    Reconcile tree entries with code map and write files to disk.
    
    Args:
        tree_entries: List of file and directory paths from ASCII tree
        code_map: Dictionary mapping file paths to code blocks
        out_root: Root directory for output
        dry_run: If True, simulate writing without creating files
        verbose: If True, log detailed information
        skip_empty: If True, skip creating placeholder files
        ignore_patterns: List of glob patterns to ignore
        files_always: Set of names to always treat as files
        dirs_always: Set of names to always treat as directories
        no_overwrite: If True, don't overwrite existing files
        heading_map: Dictionary mapping file paths to headings
        
    Returns:
        Tuple of:
        - created_dirs: Set of created directory paths
        - created_files: List of created file paths  
        - warnings: List of warning messages
        - total_lines_written: Total number of lines written
        - placeholders_created: Number of placeholder files created
        - files_written_count: Number of files actually written
    """
    # Initialize return values
    created_files: List[str] = []
    created_dirs: Set[str] = set()
    warnings: List[str] = []
    
    # Initialize counters
    total_lines_written = 0
    placeholders_created = 0
    files_written_count = 0
    
    # Normalize inputs
    ignore_patterns = ignore_patterns or []
    files_always = files_always or set()
    dirs_always = dirs_always or set()
    
    # Validate inputs
    if not tree_entries:
        warnings.append("⚠️ No tree entries provided")
        return created_dirs, created_files, warnings, total_lines_written, placeholders_created, files_written_count
    
    if not isinstance(out_root, Path):
        warnings.append("❌ Output root must be a Path object")
        return created_dirs, created_files, warnings, total_lines_written, placeholders_created, files_written_count
    
    logging.info(f"🔨 Reconciling {len(tree_entries)} entries to {out_root} (dry_run: {dry_run})")
    
    # Process each entry
    for entry in tree_entries:
        try:
            # Normalize and validate entry
            entry_clean = normalize_path_segment(entry)
            if not entry_clean:
                warnings.append(f"⚠️ Empty or invalid entry: {entry}")
                continue
            
            # Check ignore patterns
            if should_ignore_entry(entry_clean, ignore_patterns):
                if verbose:
                    logging.debug(f"⏭️  Ignored: {entry_clean}")
                continue
            
            # Determine if entry is file or directory
            name = Path(entry_clean).name
            if is_probably_file(name, files_always, dirs_always):
                # Process file entry
                file_path, lines, placeholder_flag, written_flag = process_file_entry(
                    entry_clean, out_root, code_map, heading_map,
                    dry_run, verbose, skip_empty, no_overwrite,
                    files_always, dirs_always, warnings
                )
                
                if file_path:
                    created_files.append(file_path)
                    total_lines_written += lines
                    placeholders_created += placeholder_flag
                    files_written_count += written_flag
            else:
                # Process directory entry
                dir_path = process_directory_entry(
                    entry_clean, out_root, dry_run, warnings
                )
                
                if dir_path:
                    created_dirs.add(dir_path)
                    
        except Exception as e:
            warnings.append(f"❌ Error processing entry '{entry}': {e}")
            continue
    
    # Log summary
    logging.info(
        f"✅ Reconciliation complete: "
        f"{len(created_dirs)} dirs, {len(created_files)} files, "
        f"{files_written_count} written, {placeholders_created} placeholders"
    )
    
    return created_dirs, created_files, warnings, total_lines_written, placeholders_created, files_written_count

# Debug utility function
def debug_reconciliation(
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    out_root: Path,
    files_always: Optional[Set] = None,
    dirs_always: Optional[Set] = None
) -> Dict[str, Any]:
    """
    Debug function to analyze reconciliation process.
    
    Args:
        tree_entries: Tree entries to process
        code_map: Code blocks mapping
        out_root: Output root directory
        files_always: Files always set
        dirs_always: Directories always set
        
    Returns:
        Dictionary with debug information
    """
    debug_info = {
        "tree_entries_count": len(tree_entries),
        "code_map_entries": len(code_map),
        "files_in_tree": int(0),
        "directories_in_tree": int(0),
        "files_with_content": int(0),
        "files_needing_placeholders": int(0),
        "reconciliation_stats": {}
    }
    
    # Analyze tree entries
    for entry in tree_entries:
        name = Path(entry).name
        if is_probably_file(name, files_always or set(), dirs_always or set()):
            debug_info["files_in_tree"] += 1
            if entry in code_map and code_map[entry]:
                debug_info["files_with_content"] += 1
            else:
                debug_info["files_needing_placeholders"] += 1
        else:
            debug_info["directories_in_tree"] += 1
    
    # Run reconciliation in dry-run mode
    created_dirs, created_files, warnings, lines, placeholders, written = reconcile_and_write(
        tree_entries, code_map, out_root,
        dry_run=True, verbose=False,
        files_always=files_always, dirs_always=dirs_always
    )
    
    debug_info["reconciliation_stats"] = {
        "directories_created": len(created_dirs),
        "files_created": len(created_files),
        "warnings_count": len(warnings),
        "total_lines": lines,
        "placeholders_needed": placeholders,
        "files_to_write": written
    }
    
    return debug_info