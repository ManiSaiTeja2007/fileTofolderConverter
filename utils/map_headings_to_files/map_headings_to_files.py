from typing import Dict, List, Tuple, Optional, Set, Any
from pathlib import Path
from markdown_it.token import Token
import textwrap
import re
import difflib
import logging
from functools import lru_cache

from utils.config.config import get_comment_prefix
from utils.infer_targets_from_fence_info.infer_targets_from_fence_info import infer_targets_from_fence_info
from utils.is_probably_file.is_probably_file import is_probably_file

@lru_cache(maxsize=100)
def are_hints_similar(hint1: str, hint2: str, threshold: float = 0.8) -> bool:
    """
    Check if two hints are similar using difflib with caching.
    
    Args:
        hint1: First hint string
        hint2: Second hint string
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        True if similarity >= threshold
    """
    if not hint1 or not hint2:
        return False
    return difflib.SequenceMatcher(None, hint1.lower(), hint2.lower()).ratio() >= threshold

def get_path_specificity(path: str) -> int:
    """Count path segments for specificity (e.g., 'utils/file.py' -> 2)."""
    try:
        return len(Path(path).parts)
    except Exception:
        return 0

def extract_hint_from_content(content: str) -> Tuple[str, str, bool]:
    """
    Extract hint from first line of content and return remaining body.
    
    Args:
        content: Code block content
        
    Returns:
        Tuple of (hint, body, has_hint)
    """
    if not content:
        return "", "", False
    
    lines = content.splitlines()
    if not lines:
        return "", content, False
    
    first_line = lines[0].strip()
    hint = ""
    body = content
    has_hint = False
    
    # All possible comment patterns from your config
    comment_patterns = [
        r"^\s*#\s*(.*)$",           # Python, shell, etc
        r"^\s*//\s*(.*)$",          # JavaScript, Java, etc  
        r"^\s*--\s*(.*)$",          # SQL, Haskell, etc
        r"^\s*<!--\s*(.*?)\s*-->$", # HTML/XML
        r"^\s*%\s*(.*)$",           # LaTeX
        r"^\s*\*\s*(.*)$",          # Some languages
        r"^\s*REM\s*(.*)$",         # Batch files
        r'^\s*"\s*(.*)$',           # Vim script
        r"^\s*;\s*(.*)$",           # Lisp, Assembly
    ]
    
    for pattern in comment_patterns:
        match = re.match(pattern, first_line)
        if match:
            hint = match.group(1).strip().lstrip("./").replace('\\', '/')
            body = "\n".join(lines[1:]).rstrip()
            has_hint = True
            break
    
    return hint, body, has_hint

def process_hint_replacement(
    existing_hint: str, 
    target_file: str, 
    original_content: str, 
    strip_hints: bool,
    has_existing_hint: bool
) -> Tuple[str, bool]:
    """
    Simple hint replacement: strip first line if it's a hint, replace with best hint.
    
    Args:
        existing_hint: Current hint in content (unused in this simplified version)
        target_file: Target file path  
        original_content: Original code block content
        strip_hints: Whether to strip hints
        has_existing_hint: Whether content already has a hint
        
    Returns:
        Tuple of (processed_content, was_replaced)
    """
    lines = original_content.splitlines()
    
    # If we should strip hints and there's an existing hint, remove the first line
    if strip_hints and has_existing_hint:
        body = "\n".join(lines[1:]).rstrip() if len(lines) > 1 else ""
        return body, True
    
    # If there's an existing hint, always replace it with the target file
    if has_existing_hint:
        body = "\n".join(lines[1:]).rstrip() if len(lines) > 1 else ""
        try:
            file_extension = Path(target_file).suffix.lstrip('.')
            comment_prefix = get_comment_prefix(file_extension or Path(target_file).name.lower())
        except Exception as e:
            logging.warning(f"⚠️ Failed to get comment prefix for '{target_file}': {e}")
            comment_prefix = "# "  # Fallback
        
        return f"{comment_prefix}{target_file}\n{body}", True
    
    # If no existing hint and we shouldn't strip, add the target file as hint
    if not strip_hints:
        try:
            file_extension = Path(target_file).suffix.lstrip('.')
            comment_prefix = get_comment_prefix(file_extension or Path(target_file).name.lower())
        except Exception as e:
            logging.warning(f"⚠️ Failed to get comment prefix for '{target_file}': {e}")
            comment_prefix = "# "  # Fallback
        
        return f"{comment_prefix}{target_file}\n{original_content}", True
    
    # Default: return original content unchanged
    return original_content, False

def build_basename_lookup(code_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Build lookup dictionary from basename to full paths.
    
    Args:
        code_map: Mapping of file paths to code blocks
        
    Returns:
        Dictionary mapping basenames to lists of full paths
    """
    basename_lookup: Dict[str, List[str]] = {}
    for file_path in code_map.keys():
        try:
            basename = Path(file_path).name
            basename_lookup.setdefault(basename, []).append(file_path)
        except Exception as e:
            logging.warning(f"⚠️ Failed to process path {file_path}: {e}")
    return basename_lookup

def handle_heading_mapping(
    heading_text: str,
    heading_text_stripped: str,
    code_map: Dict[str, List[str]],
    basename_lookup: Dict[str, List[str]],
    heading_map: Dict[str, str]
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Handle mapping of heading to file with multiple matching strategies.
    
    Args:
        heading_text: Original heading text
        heading_text_stripped: Normalized heading text
        code_map: File to code blocks mapping
        basename_lookup: Basename to paths lookup
        heading_map: Heading mapping dictionary
        
    Returns:
        Tuple of (current_file, current_heading, warnings)
    """
    warnings: List[str] = []
    
    # 1. Exact match
    if heading_text_stripped in code_map:
        heading_map[heading_text_stripped] = heading_text
        return heading_text_stripped, heading_text, warnings
    
    # 2. Partial path matches
    candidates = [
        f for f in code_map.keys() 
        if heading_text_stripped.endswith(f) or f.endswith(heading_text_stripped)
    ]
    if len(candidates) == 1:
        heading_map[candidates[0]] = heading_text
        warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{candidates[0]}' via partial path")
        return candidates[0], heading_text, warnings
    elif len(candidates) > 1:
        warnings.append(f"⚠️ Ambiguous heading '{heading_text}' matches multiple files: {candidates}")
        return None, None, warnings
    
    # 3. Basename match
    try:
        basename = Path(heading_text_stripped).name
        if basename in basename_lookup and len(basename_lookup[basename]) == 1:
            target_file = basename_lookup[basename][0]
            heading_map[target_file] = heading_text
            warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{target_file}' via basename")
            return target_file, heading_text, warnings
    except Exception as e:
        logging.debug(f"⚠️ Error in basename matching for '{heading_text_stripped}': {e}")
    
    # 4. Fuzzy matching fallback
    try:
        fuzzy_matches = difflib.get_close_matches(
            heading_text_stripped, list(code_map.keys()), n=1, cutoff=0.8
        )
        if fuzzy_matches:
            heading_map[fuzzy_matches[0]] = heading_text
            warnings.append(f"ℹ️ Fuzzy matched heading '{heading_text}' to file '{fuzzy_matches[0]}'")
            return fuzzy_matches[0], heading_text, warnings
    except Exception as e:
        logging.debug(f"⚠️ Error in fuzzy matching for '{heading_text_stripped}': {e}")
    
    warnings.append(f"⚠️ Heading '{heading_text}' does not match any file in tree")
    return None, None, warnings

def handle_fence_with_current_file(
    fence_content: str,
    current_file: str,
    code_map: Dict[str, List[str]],
    strip_hints: bool,
    warnings: List[str]
) -> bool:
    """
    Handle fence block when there's an active current file.
    
    Args:
        fence_content: Code block content
        current_file: Currently active file
        code_map: File to code blocks mapping
        strip_hints: Whether to strip hints
        warnings: Warnings list to append to
        
    Returns:
        True if successfully handled
    """
    if current_file not in code_map:
        return False
    
    hint, body, has_hint = extract_hint_from_content(fence_content)
    processed_content, was_replaced = process_hint_replacement(
        hint, current_file, fence_content, strip_hints, has_hint
    )
    
    if was_replaced:
        if strip_hints:
            warnings.append(f"ℹ️ Stripped hint '{hint}' from code block")
        else:
            warnings.append(f"ℹ️ Replaced hint '{hint}' with '{current_file}' (more specific)")
    
    if processed_content:
        # Check if the last block already has the same hint to avoid duplicates
        existing_blocks = code_map[current_file]
        if existing_blocks:
            last_block = existing_blocks[-1]
            last_hint, _, last_has_hint = extract_hint_from_content(last_block)
            if (last_has_hint and has_hint and 
                are_hints_similar(last_hint, hint) and 
                not strip_hints):
                warnings.append(f"⚠️ File {current_file} had multiple code blocks with similar hints")
        
        code_map[current_file].append(processed_content)
    
    return True

def handle_fence_with_info(
    fence_info: str,
    fence_content: str,
    code_map: Dict[str, List[str]],
    basename_lookup: Dict[str, List[str]],
    heading_map: Dict[str, str],
    strip_hints: bool,
    warnings: List[str],
    unassigned: List[str]
) -> bool:
    """
    Handle fence block using fence info for inference.
    
    Args:
        fence_info: Fence info string
        fence_content: Code block content
        code_map: File to code blocks mapping
        basename_lookup: Basename to paths lookup
        heading_map: Heading mapping dictionary
        strip_hints: Whether to strip hints
        warnings: Warnings list to append to
        unassigned: Unassigned blocks list to append to
        
    Returns:
        True if successfully handled
    """
    if not fence_info:
        return False
    
    try:
        candidates = infer_targets_from_fence_info(fence_info, list(code_map.keys()))
        
        # Try exact basename matches first
        exact_matches = [c for c in candidates if Path(c).name.lower() == fence_info.lower()]
        if exact_matches:
            return assign_fence_to_target(
                exact_matches[0], fence_info, fence_content, code_map, 
                heading_map, strip_hints, warnings, "exact"
            )
        
        # Single candidate match
        if len(candidates) == 1:
            return assign_fence_to_target(
                candidates[0], fence_info, fence_content, code_map,
                heading_map, strip_hints, warnings, "inferred"
            )
        
        # Multiple candidates
        if len(candidates) > 1:
            warnings.append(f"⚠️ Ambiguous fence info '{fence_info}' matches {candidates}; kept unassigned")
            unassigned.append(fence_content)
            return True
        
    except Exception as e:
        warnings.append(f"⚠️ Failed to infer targets from fence info '{fence_info}': {e}")
        unassigned.append(fence_content)
        return True
    
    return False

def assign_fence_to_target(
    target: str,
    source_info: str,
    fence_content: str,
    code_map: Dict[str, List[str]],
    heading_map: Dict[str, str],
    strip_hints: bool,
    warnings: List[str],
    match_type: str
) -> bool:
    """
    Assign a fence block to a specific target file.
    
    Args:
        target: Target file path
        source_info: Source information (fence info or hint)
        fence_content: Code block content
        code_map: File to code blocks mapping
        heading_map: Heading mapping dictionary
        strip_hints: Whether to strip hints
        warnings: Warnings list to append to
        match_type: Type of match for logging
        
    Returns:
        True if successfully assigned
    """
    if target not in code_map:
        return False
    
    hint, body, has_hint = extract_hint_from_content(fence_content)
    processed_content, was_replaced = process_hint_replacement(
        hint, target, fence_content, strip_hints, has_hint
    )
    
    if was_replaced:
        if strip_hints:
            warnings.append(f"ℹ️ Stripped hint '{hint}' from code block")
        else:
            warnings.append(f"ℹ️ Replaced hint '{hint}' with '{target}' (more specific)")
    
    if processed_content:
        # Check if the last block already has the same hint to avoid duplicates
        existing_blocks = code_map[target]
        if existing_blocks:
            last_block = existing_blocks[-1]
            last_hint, _, last_has_hint = extract_hint_from_content(last_block)
            if (last_has_hint and has_hint and 
                are_hints_similar(last_hint, hint) and 
                not strip_hints):
                warnings.append(f"⚠️ File {target} had multiple code blocks with similar hints")
        
        code_map[target].append(processed_content)
        heading_map[target] = source_info
        
        if match_type == "exact":
            warnings.append(f"ℹ️ Assigned fenced block (exact info='{source_info}') -> {target}")
        else:
            warnings.append(f"ℹ️ Assigned fenced block (info='{source_info}') -> {target}")
    
    return True

def map_headings_to_files(
    tokens: List[Token],
    tree_files: List[str],
    files_always: Set[str],
    dirs_always: Set[str],
    strip_hints: bool = False,
    interactive: bool = False
) -> Tuple[Dict[str, List[str]], List[str], List[str], Dict[str, str]]:
    """
    Map Markdown headings and code blocks to files in the tree, handling hints and fuzzy matching.
    
    Args:
        tokens: List of Markdown tokens.
        tree_files: List of file paths from the ASCII tree.
        files_always: Set of names to treat as files.
        dirs_always: Set of names to treat as directories.
        strip_hints: Whether to strip first-line hint comments.
        interactive: Whether to prompt for conflict resolution.
        
    Returns:
        Tuple of (code_map, unassigned, warnings, heading_map):
            - code_map: Dict mapping file paths to lists of code block contents.
            - unassigned: List of unassigned code blocks.
            - warnings: List of warnings for ambiguous matches or hint handling.
            - heading_map: Dict mapping file paths to their corresponding headings.
    """
    # Input validation
    if not tokens or not tree_files:
        return {}, [], [], {}
    
    # Initialize data structures
    code_map: Dict[str, List[str]] = {}
    for file_path in tree_files:
        try:
            if is_probably_file(Path(file_path).name, files_always, dirs_always):
                code_map[file_path] = []
        except Exception as e:
            logging.warning(f"⚠️ Failed to process tree file {file_path}: {e}")
    
    heading_map: Dict[str, str] = {}
    unassigned: List[str] = []
    warnings: List[str] = []
    
    # Build lookup structures
    basename_lookup = build_basename_lookup(code_map)
    
    # State tracking
    current_file: Optional[str] = None
    current_heading: Optional[str] = None
    skip_next_fence_for_file_structure = False
    
    # Process tokens
    i = 0
    n = len(tokens)
    
    while i < n:
        try:
            tok = tokens[i]
            
            # Heading handling
            if tok.type == "heading_open":
                inline = tokens[i + 1] if (i + 1) < n else None
                heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
                heading_text_stripped = heading_text.strip().replace('\\', '/').lstrip("./")
                
                if heading_text_stripped.lower() == "file structure":
                    current_file = None
                    current_heading = None
                    skip_next_fence_for_file_structure = True
                else:
                    current_file, current_heading, heading_warnings = handle_heading_mapping(
                        heading_text, heading_text_stripped, code_map, basename_lookup, heading_map
                    )
                    warnings.extend(heading_warnings)
                
                i += 1
                continue
            
            # Fence blocks
            if tok.type == "fence":
                fence_info = getattr(tok, "info", "") or ""
                fence_info = fence_info.strip()
                fence_content = textwrap.dedent(tok.content).rstrip()
                # Unescape backticks to restore original content
                fence_content = fence_content.replace(r"\\```", r"```")
                
                if skip_next_fence_for_file_structure:
                    skip_next_fence_for_file_structure = False
                    i += 1
                    continue
                
                # Try current file first
                if current_file and current_file in code_map:
                    if handle_fence_with_current_file(
                        fence_content, current_file, code_map, strip_hints, warnings
                    ):
                        i += 1
                        continue
                
                # Try fence info inference
                if handle_fence_with_info(
                    fence_info, fence_content, code_map, basename_lookup,
                    heading_map, strip_hints, warnings, unassigned
                ):
                    i += 1
                    continue
                
                # Try hint in first line
                hint, body, has_hint = extract_hint_from_content(fence_content)
                if hint:
                    candidates = [f for f in code_map.keys() if f.endswith(hint) or hint in f]
                    if len(candidates) == 1:
                        if assign_fence_to_target(
                            candidates[0], hint, fence_content, code_map,
                            heading_map, strip_hints, warnings, "hint"
                        ):
                            i += 1
                            continue
                    elif len(candidates) > 1:
                        warnings.append(f"⚠️ Ambiguous hint '{hint}' matches {candidates}; kept unassigned")
                        unassigned.append(fence_content)
                        i += 1
                        continue
                
                # Try basename from fence info
                if fence_info:
                    fence_basename = Path(fence_info).name
                    if (fence_basename in basename_lookup and 
                        len(basename_lookup[fence_basename]) == 1):
                        if assign_fence_to_target(
                            basename_lookup[fence_basename][0], fence_basename, fence_content,
                            code_map, heading_map, strip_hints, warnings, "basename"
                        ):
                            i += 1
                            continue
                
                # Fallback to unassigned
                unassigned.append(fence_content)
                i += 1
                continue
            
            # Handle paragraphs under headings as potential content
            if tok.type == "paragraph_open" and current_file and current_file in code_map:
                inline = tokens[i + 1] if (i + 1) < n else None
                para_text = inline.content.strip() if inline and inline.type == "inline" else ""
                if para_text:
                    hint, _, has_hint = extract_hint_from_content(code_map[current_file][-1]) if code_map[current_file] else ("", "", False)
                    if (code_map[current_file] and 
                        are_hints_similar(hint, current_file)):
                        warnings.append(f"⚠️ File {current_file} had multiple code blocks merged")
                    code_map[current_file].append(para_text)
                
                # Skip to paragraph close
                j = i + 1
                while j < n and tokens[j].type != "paragraph_close":
                    j += 1
                i = j + 1
                continue
            
            i += 1
            
        except Exception as e:
            logging.warning(f"⚠️ Error processing token at index {i}: {e}")
            i += 1
    
    logging.info(f"✅ Mapping complete: {len(code_map)} files, {len(unassigned)} unassigned blocks")
    return code_map, unassigned, warnings, heading_map

# Debug utility
def debug_mapping_process(
    tokens: List[Token],
    tree_files: List[str],
    files_always: Set[str],
    dirs_always: Set[str]
) -> Dict[str, Any]:
    """
    Debug function to analyze the mapping process.
    
    Args:
        tokens: Markdown tokens
        tree_files: Tree file paths
        files_always: Files always set
        dirs_always: Directories always set
        
    Returns:
        Dictionary with debug information
    """
    debug_info = {
        "tokens_count": len(tokens),
        "tree_files_count": len(tree_files),
        "files_in_code_map": 0,
        "headings_found": 0,
        "fence_blocks_found": 0,
        "mapping_strategy_breakdown": {}
    }
    
    # Count headings and fences
    debug_info["headings_found"] = sum(1 for t in tokens if t.type == "heading_open")
    debug_info["fence_blocks_found"] = sum(1 for t in tokens if t.type == "fence")
    
    # Run mapping
    code_map, unassigned, warnings, heading_map = map_headings_to_files(
        tokens, tree_files, files_always, dirs_always
    )
    
    debug_info["files_in_code_map"] = len(code_map)
    debug_info["unassigned_blocks"] = len(unassigned)
    debug_info["warnings_count"] = len(warnings)
    debug_info["heading_map_entries"] = len(heading_map)
    
    return debug_info