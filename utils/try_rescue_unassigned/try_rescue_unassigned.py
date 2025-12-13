from typing import List, Tuple, Dict, Optional
import re
import difflib
from pathlib import Path
import logging

from utils.resolve_conflict_interactive.resolve_conflict_interactive import resolve_conflict_interactive
from utils.config.config import get_comment_prefix, get_comment_suffix

def extract_hint_from_code(code: str, max_lines: int = 2) -> Tuple[Optional[str], int]:
    """
    Extract hint from code block comments in first few lines.
    
    Args:
        code: Code block content
        max_lines: Maximum number of lines to check for hints
        
    Returns:
        Tuple of (hint, line_number) or (None, -1) if no hint found
    """
    if not code or not code.strip():
        return None, -1
    
    lines = code.splitlines()
    
    # Check first few lines for comment-style hints
    for line_num in range(min(max_lines, len(lines))):
        line = lines[line_num].strip()
        
        # Match various comment styles
        match = re.match(r"^(\s*//\s*|\s*#\s*|\s*<!--\s*|\s*/\*\s*)(.*?)(\s*-->|\s*\*/)?$", line)
        if match:
            hint = match.group(2).strip().lstrip("./").replace('\\', '/')
            if hint:  # Only return non-empty hints
                return hint, line_num
    
    return None, -1

def find_matching_files(
    hint: str, 
    code_map: Dict[str, List[str]], 
    fallback_level: str
) -> List[str]:
    """
    Find files that match a hint using multiple strategies.
    
    Args:
        hint: Hint to match against files
        code_map: Mapping of files to code blocks
        fallback_level: Matching strictness level
        
    Returns:
        List of matching file paths
    """
    candidates = []
    
    # Strategy 1: Exact path match
    if hint in code_map:
        return [hint]
    
    # Strategy 2: Suffix match (file ends with hint)
    candidates = [f for f in code_map.keys() if f.endswith(hint)]
    if candidates:
        return candidates
    
    # Strategy 3: Substring match (for medium/high fallback)
    if fallback_level in ("medium", "high"):
        candidates = [f for f in code_map.keys() if hint in f]
        if candidates:
            return candidates
    
    # Strategy 4: Fuzzy matching (for medium/high fallback)
    if fallback_level in ("medium", "high"):
        fuzzy_matches = difflib.get_close_matches(hint, code_map.keys(), n=3, cutoff=0.7)
        if fuzzy_matches:
            return fuzzy_matches
    
    return []

def process_hint_match(
    code: str,
    hint: str,
    hint_line_num: int,
    target: str,
    code_map: Dict[str, List[str]],
    strip_hints: bool,
    rescued_warnings: List[str]
) -> bool:
    """
    Process a successful hint match and assign code to target file.
    
    Args:
        code: Original code content
        hint: Extracted hint
        hint_line_num: Line number where hint was found
        target: Target file path
        code_map: Code mapping to update
        strip_hints: Whether to remove hints
        rescued_warnings: Warnings list to append to
        
    Returns:
        True if successfully assigned
    """
    try:
        lines = code.splitlines()
        existing_hint = hint if hint_line_num >= 0 else ""
        
        # Process content based on hint matching and strip settings
        if existing_hint and are_hints_similar(existing_hint, target):
            # Determine if we should keep or replace the hint
            if get_path_specificity(existing_hint) >= get_path_specificity(target):
                body = code  # Keep original content
            else:
                # Replace with more specific hint or strip
                if strip_hints:
                    body = "\n".join(
                        lines[:hint_line_num] + lines[hint_line_num + 1:]
                    ).rstrip()
                else:
                    ext = Path(target).suffix.lower()
                    prefix = get_comment_prefix(ext)
                    suffix = get_comment_suffix(ext)
                    body = f"{prefix}{target}{suffix}\n{code.lstrip()}"
                rescued_warnings.append(f"ℹ️ Replaced hint '{existing_hint}' with '{target}' (more specific)")
        elif strip_hints and hint_line_num >= 0:
            # Strip hint without replacement
            body = "\n".join(
                lines[:hint_line_num] + lines[hint_line_num + 1:]
            ).rstrip()
        else:
            body = code  # Keep original content
        
        # Add to code map with duplicate check
        if body:
            if (code_map[target] and 
                are_hints_similar(code_map[target][-1].splitlines()[0], target)):
                rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
            
            code_map[target].append(body)
            rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from hint '{hint}')")
            return True
    
    except Exception as e:
        logging.warning(f"⚠️ Error processing hint match for '{hint}': {e}")
    
    return False

def try_basename_match(
    code: str,
    hint: str,
    hint_line_num: int,
    code_map: Dict[str, List[str]],
    strip_hints: bool,
    rescued_warnings: List[str]
) -> bool:
    """
    Try to match by basename when full path matching fails.
    
    Args:
        code: Code content
        hint: Original hint
        hint_line_num: Hint line number
        code_map: Code mapping
        strip_hints: Whether to strip hints
        rescued_warnings: Warnings list
        
    Returns:
        True if matched by basename
    """
    basename = Path(hint).name
    basename_matches = [f for f in code_map.keys() if Path(f).name == basename]
    
    if len(basename_matches) == 1:
        target = basename_matches[0]
        body = (
            "\n".join(
                code.splitlines()[:hint_line_num] + 
                code.splitlines()[hint_line_num + 1:]
            ).rstrip() 
            if strip_hints and hint_line_num >= 0 
            else code
        )
        
        if body:
            if (code_map[target] and 
                are_hints_similar(code_map[target][-1].splitlines()[0], target)):
                rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
            
            code_map[target].append(body)
            rescued_warnings.append(f"ℹ️ Auto-assigned block to {target} (basename match for hint '{hint}')")
            return True
    
    return False

def try_heading_match(
    code: str,
    heading_map: Dict[str, str],
    code_map: Dict[str, List[str]],
    strip_hints: bool,
    rescued_warnings: List[str]
) -> bool:
    """
    Try to match code block using heading map.
    
    Args:
        code: Code content
        heading_map: Heading to file mapping
        code_map: Code mapping
        strip_hints: Whether to strip hints
        rescued_warnings: Warnings list
        
    Returns:
        True if matched by heading
    """
    lines = code.splitlines()
    if not lines:
        return False
    
    first_line = lines[0].strip()
    
    for target, heading in heading_map.items():
        if target not in code_map:
            continue
            
        heading_clean = heading.strip().lstrip("./").replace('\\', '/')
        if first_line.startswith(heading) or heading_clean in first_line:
            body = "\n".join(lines[1:]).rstrip() if strip_hints else code
        
            if body:
                if (code_map[target] and 
                    are_hints_similar(code_map[target][-1].splitlines()[0], target)):
                    rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                
                code_map[target].append(body)
                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from heading '{heading}')")
                return True
    
    return False

# Helper functions (keep these from original)
def get_path_specificity(path: str) -> int:
    """Count path segments for specificity (e.g., 'utils/file.py' -> 2)."""
    return len(Path(path).parts)

def are_hints_similar(hint1: str, hint2: str, threshold: float = 0.8) -> bool:
    """Check if two hints are similar using difflib."""
    if not hint1 or not hint2:
        return False
    return difflib.SequenceMatcher(None, hint1.lower(), hint2.lower()).ratio() >= threshold

def try_rescue_unassigned(
    unassigned: List[str],
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    heading_map: Dict[str, str],
    strip_hints: bool = False,
    interactive: bool = False,
    fallback_level: str = "high",
) -> Tuple[List[str], List[str]]:
    """
    Attempt to rescue unassigned code blocks by matching hints or headings.
    
    Args:
        unassigned: List of unassigned code blocks.
        tree_entries: List of file paths from the ASCII tree.
        code_map: Dict mapping file paths to lists of code block contents.
        heading_map: Dict mapping file paths to their corresponding headings.
        strip_hints: Whether to strip first-line hint comments.
        interactive: Whether to prompt for conflict resolution.
        fallback_level: Rescue strictness ('low': exact matches, 'medium': fuzzy matches, 'high': auto-assign).
        
    Returns:
        Tuple of (still_unassigned, rescued_warnings): Unassigned blocks and warnings.
    """
    # Input validation
    if not unassigned:
        return [], ["ℹ️ No unassigned blocks to rescue"]
    
    if not code_map:
        return unassigned, ["⚠️ No code map available for rescue attempts"]
    
    rescued_warnings: List[str] = []
    still_unassigned: List[str] = []
    
    logging.info(f"🔍 Attempting to rescue {len(unassigned)} unassigned blocks (fallback: {fallback_level})")
    
    for code in unassigned:
        if not code or not code.strip():
            rescued_warnings.append("⚠️ Skipped empty code block")
            continue
        
        try:
            # Step 1: Extract hint from comments
            hint, hint_line_num = extract_hint_from_code(code)
            
            if hint:
                # Step 2: Find matching files for the hint
                candidates = find_matching_files(hint, code_map, fallback_level)
                
                if len(candidates) == 1:
                    # Single match - assign directly
                    if process_hint_match(code, hint, hint_line_num, candidates[0], 
                                        code_map, strip_hints, rescued_warnings):
                        continue
                
                elif len(candidates) > 1:
                    # Multiple matches - need resolution
                    if interactive:
                        selected = resolve_conflict_interactive(hint, candidates)
                        if selected and process_hint_match(code, hint, hint_line_num, selected,
                                                         code_map, strip_hints, rescued_warnings):
                            continue
                    else:
                        rescued_warnings.append(f"⚠️ Ambiguous hint '{hint}' matches {candidates}; kept unassigned")
                        still_unassigned.append(code)
                        continue
                
                else:
                    # No matches found
                    rescued_warnings.append(f"⚠️ Hint '{hint}' did not match any file")
                    
                    # Try basename matching for high fallback
                    if (fallback_level == "high" and 
                        try_basename_match(code, hint, hint_line_num, code_map, strip_hints, rescued_warnings)):
                        continue
                    
                    still_unassigned.append(code)
                    continue
            
            # Step 3: Try first line as assumed heading (for medium/high fallback)
            if fallback_level in ("medium", "high"):
                lines = code.splitlines()
                if lines:
                    assumed_hint = lines[0].strip().lstrip("./").replace('\\', '/')
                    candidates = find_matching_files(assumed_hint, code_map, fallback_level)
                    
                    if len(candidates) == 1:
                        body = "\n".join(lines[1:]).rstrip() if strip_hints else code
                        if body:
                            if (code_map[candidates[0]] and 
                                are_hints_similar(code_map[candidates[0]][-1].splitlines()[0], candidates[0])):
                                rescued_warnings.append(f"⚠️ File {candidates[0]} had multiple code blocks merged")
                            
                            code_map[candidates[0]].append(body)
                            rescued_warnings.append(f"ℹ️ Rescued block → assigned to {candidates[0]} (from assumed heading '{assumed_hint}')")
                            continue
                    
                    elif len(candidates) > 1 and interactive:
                        selected = resolve_conflict_interactive(assumed_hint, candidates)
                        if selected:
                            body = "\n".join(lines[1:]).rstrip() if strip_hints else code
                            if body:
                                code_map[selected].append(body)
                                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {selected} (interactive selection)")
                                continue
            
            # Step 4: Try heading map matching (for medium/high fallback)
            if (fallback_level in ("medium", "high") and 
                try_heading_match(code, heading_map, code_map, strip_hints, rescued_warnings)):
                continue
            
            # Step 5: Final fallback - content-based matching (high only)
            if fallback_level == "high":
                # Simple content-based assignment to least used file
                target_files = [f for f in code_map.keys() if len(code_map[f]) == 0]
                if target_files:
                    target = target_files[0]  # Pick first empty file
                    code_map[target].append(code)
                    rescued_warnings.append(f"ℹ️ Auto-assigned block to {target} (fallback assignment)")
                    continue
            
            # If all strategies fail, keep unassigned
            still_unassigned.append(code)
            
        except Exception as e:
            logging.error(f"❌ Error rescuing code block: {e}")
            rescued_warnings.append(f"⚠️ Error processing code block: {e}")
            still_unassigned.append(code)
    
    logging.info(f"✅ Rescue complete: {len(unassigned) - len(still_unassigned)}/{len(unassigned)} blocks rescued")
    return still_unassigned, rescued_warnings