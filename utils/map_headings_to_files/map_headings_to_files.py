from typing import Dict, List, Tuple, Optional, Set, Any, Pattern
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

# ============================================================================
# String Similarity Utilities
# ============================================================================

@lru_cache(maxsize=100)
def calculate_string_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity ratio between two strings (0.0 to 1.0).
    
    Args:
        str1: First string
        str2: Second string
        
    Returns:
        Similarity ratio
    """
    if not str1 or not str2:
        return 0.0
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def are_strings_similar(str1: str, str2: str, threshold: float = 0.8) -> bool:
    """
    Check if two strings are similar above a given threshold.
    
    Args:
        str1: First string
        str2: Second string
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        True if similarity >= threshold
    """
    return calculate_string_similarity(str1, str2) >= threshold

# ============================================================================
# Path Utilities
# ============================================================================

def get_path_specificity(path: str) -> int:
    """Count path segments for specificity (e.g., 'utils/file.py' -> 2)."""
    try:
        return len(Path(path).parts)
    except Exception:
        return 0

def normalize_path_string(path_str: str) -> str:
    """
    Normalize a path string for consistent comparison.
    
    Args:
        path_str: Raw path string
        
    Returns:
        Normalized path string
    """
    if not path_str:
        return ""
    
    # Replace backslashes with forward slashes
    normalized = path_str.replace('\\', '/')
    # Remove leading ./ or .\
    normalized = normalized.lstrip('./')
    # Remove trailing slashes
    normalized = normalized.rstrip('/')
    
    return normalized

# ============================================================================
# Markdown Formatting Cleanup
# ============================================================================

def clean_markdown_formatting(text: str) -> str:
    """
    Remove common markdown formatting from text.
    
    Args:
        text: Text with potential markdown formatting
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove bold formatting: **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    # Remove italic formatting: *text* or _text_
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Remove inline code: `text`
    text = re.sub(r'`(.*?)`', r'\1', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove any remaining asterisks or underscores
    text = text.replace('*', '').replace('_', '')
    
    return text.strip()

# ============================================================================
# Comment/Hint Extraction Utilities
# ============================================================================

COMMENT_PATTERNS: List[Tuple[Pattern, str]] = [
    (re.compile(r'^\s*#\s*(.*)$'), '#'),          # Python, shell, etc
    (re.compile(r'^\s*//\s*(.*)$'), '//'),        # JavaScript, Java, etc  
    (re.compile(r'^\s*--\s*(.*)$'), '--'),        # SQL, Haskell, etc
    (re.compile(r'^\s*<!--\s*(.*?)\s*-->$'), '<!--'), # HTML/XML
    (re.compile(r'^\s*%\s*(.*)$'), '%'),          # LaTeX
    (re.compile(r'^\s*\*\s*(.*)$'), '*'),         # Some languages
    (re.compile(r'^\s*REM\s*(.*)$'), 'REM'),      # Batch files
    (re.compile(r'^\s*"\s*(.*)$'), '"'),          # Vim script
    (re.compile(r'^\s*;\s*(.*)$'), ';'),          # Lisp, Assembly
]

def extract_hint_from_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract hint from a line if it contains a comment.
    
    Args:
        line: Line to analyze
        
    Returns:
        Tuple of (hint, comment_prefix) or (None, None) if no comment
    """
    line = line.rstrip()
    
    for pattern, prefix in COMMENT_PATTERNS:
        match = pattern.match(line)
        if match:
            hint = match.group(1).strip()
            if hint:
                # Normalize the hint as a path
                hint = normalize_path_string(hint)
                return hint, prefix
    
    return None, None

def extract_hint_and_body(content: str) -> Tuple[str, str, bool]:
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
    
    first_line = lines[0]
    hint, comment_prefix = extract_hint_from_line(first_line)
    
    if hint is not None and comment_prefix is not None:
        body = "\n".join(lines[1:]).rstrip() if len(lines) > 1 else ""
        return hint, body, True
    
    return "", content, False

def format_hint_comment(file_path: str, file_extension: str = "") -> str:
    """
    Format a file path as a comment hint.
    
    Args:
        file_path: Target file path
        file_extension: File extension for comment style
        
    Returns:
        Formatted comment string
    """
    try:
        if not file_extension:
            file_extension = Path(file_path).suffix.lstrip('.') or Path(file_path).name.lower()
        
        comment_prefix = get_comment_prefix(file_extension)
        return f"{comment_prefix}{file_path}"
    except Exception as e:
        logging.warning(f"⚠️ Failed to get comment prefix for '{file_path}': {e}")
        return f"# {file_path}"  # Fallback to Python-style comment

# ============================================================================
# Content Processing Utilities
# ============================================================================

def process_code_block_content(
    content: str,
    target_file: str,
    strip_hints: bool,
    has_existing_hint: bool
) -> Tuple[str, bool, Optional[str]]:
    """
    Process code block content for hint handling.
    
    Args:
        content: Original code block content
        target_file: Target file path
        strip_hints: Whether to strip hints
        has_existing_hint: Whether content already has a hint
        
    Returns:
        Tuple of (processed_content, was_modified, original_hint)
    """
    lines = content.splitlines()
    original_hint = None
    
    # Extract existing hint if present
    if has_existing_hint and lines:
        hint, _ = extract_hint_from_line(lines[0])
        original_hint = hint
    
    # Case 1: Strip hints if requested and exists
    if strip_hints and has_existing_hint:
        body = "\n".join(lines[1:]).rstrip() if len(lines) > 1 else ""
        return body, True, original_hint
    
    # Case 2: Replace existing hint with target file
    if has_existing_hint:
        body = "\n".join(lines[1:]).rstrip() if len(lines) > 1 else ""
        file_extension = Path(target_file).suffix.lstrip('.')
        hint_comment = format_hint_comment(target_file, file_extension)
        return f"{hint_comment}\n{body}", True, original_hint
    
    # Case 3: Add hint if not stripping
    if not strip_hints:
        file_extension = Path(target_file).suffix.lstrip('.')
        hint_comment = format_hint_comment(target_file, file_extension)
        return f"{hint_comment}\n{content}", True, None
    
    # Case 4: No changes needed
    return content, False, None

# ============================================================================
# Lookup Structures
# ============================================================================

class PathLookup:
    """Helper class for efficient path lookups."""
    
    def __init__(self, file_paths: List[str]):
        self.file_paths = file_paths
        self.basename_map: Dict[str, List[str]] = {}
        self.path_parts_map: Dict[str, List[str]] = {}
        self._build_lookups()
    
    def _build_lookups(self):
        """Build lookup dictionaries."""
        for file_path in self.file_paths:
            try:
                # Basename lookup
                basename = Path(file_path).name
                self.basename_map.setdefault(basename, []).append(file_path)
                
                # Path parts lookup for partial matching
                path_parts = Path(file_path).parts
                for i in range(1, len(path_parts) + 1):
                    partial_path = str(Path(*path_parts[-i:]))
                    self.path_parts_map.setdefault(partial_path, []).append(file_path)
            except Exception as e:
                logging.warning(f"⚠️ Failed to process path {file_path}: {e}")
    
    def find_by_exact_path(self, path: str) -> Optional[str]:
        """Find file by exact path match."""
        normalized_path = normalize_path_string(path)
        if normalized_path in self.file_paths:
            return normalized_path
        return None
    
    def find_by_basename(self, basename: str) -> List[str]:
        """Find files by basename."""
        return self.basename_map.get(basename, [])
    
    def find_by_partial_path(self, partial_path: str) -> List[str]:
        """Find files by partial path match."""
        normalized_partial = normalize_path_string(partial_path)
        return self.path_parts_map.get(normalized_partial, [])
    
    def find_by_fuzzy_match(self, query: str, threshold: float = 0.8, limit: int = 3) -> List[str]:
        """Find files by fuzzy matching."""
        matches = []
        query_lower = query.lower()
        
        for file_path in self.file_paths:
            similarity = calculate_string_similarity(query_lower, file_path.lower())
            if similarity >= threshold:
                matches.append((file_path, similarity))
        
        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        return [path for path, _ in matches[:limit]]

# ============================================================================
# Heading Mapping Logic
# ============================================================================

class HeadingMapper:
    """Handles mapping between headings and files."""
    
    def __init__(self, path_lookup: PathLookup):
        self.path_lookup = path_lookup
        self.heading_to_file: Dict[str, str] = {}
        self.file_to_heading: Dict[str, str] = {}
    
    def map_heading_to_file(
        self, 
        heading_text: str, 
        heading_clean: str
    ) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Map a heading to a file using multiple strategies.
        
        Args:
            heading_text: Original heading text with formatting
            heading_clean: Cleaned heading text without markdown
            
        Returns:
            Tuple of (mapped_file, original_heading, warnings)
        """
        warnings: List[str] = []
        
        # Strategy 1: Exact path match
        exact_match = self.path_lookup.find_by_exact_path(heading_clean)
        if exact_match:
            self._register_mapping(exact_match, heading_text)
            return exact_match, heading_text, warnings
        
        # Strategy 2: Partial path match
        partial_matches = self.path_lookup.find_by_partial_path(heading_clean)
        if len(partial_matches) == 1:
            self._register_mapping(partial_matches[0], heading_text)
            warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{partial_matches[0]}' via partial path")
            return partial_matches[0], heading_text, warnings
        elif len(partial_matches) > 1:
            warnings.append(f"⚠️ Ambiguous heading '{heading_text}' matches multiple files: {partial_matches}")
            return None, None, warnings
        
        # Strategy 3: Basename match
        try:
            basename = Path(heading_clean).name
            basename_matches = self.path_lookup.find_by_basename(basename)
            if len(basename_matches) == 1:
                self._register_mapping(basename_matches[0], heading_text)
                warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{basename_matches[0]}' via basename")
                return basename_matches[0], heading_text, warnings
        except Exception as e:
            logging.debug(f"⚠️ Error in basename matching for '{heading_clean}': {e}")
        
        # Strategy 4: Fuzzy matching
        fuzzy_matches = self.path_lookup.find_by_fuzzy_match(heading_clean, threshold=0.8, limit=1)
        if fuzzy_matches:
            self._register_mapping(fuzzy_matches[0], heading_text)
            warnings.append(f"ℹ️ Fuzzy matched heading '{heading_text}' to file '{fuzzy_matches[0]}'")
            return fuzzy_matches[0], heading_text, warnings
        
        warnings.append(f"⚠️ Heading '{heading_text}' does not match any file in tree")
        return None, None, warnings
    
    def _register_mapping(self, file_path: str, heading_text: str):
        """Register a bidirectional mapping."""
        self.heading_to_file[heading_text] = file_path
        self.file_to_heading[file_path] = heading_text
    
    def get_file_for_heading(self, heading_text: str) -> Optional[str]:
        """Get mapped file for a heading."""
        return self.heading_to_file.get(heading_text)
    
    def get_heading_for_file(self, file_path: str) -> Optional[str]:
        """Get mapped heading for a file."""
        return self.file_to_heading.get(file_path)

# ============================================================================
# Fence Block Processing
# ============================================================================

class FenceBlockProcessor:
    """Processes fence blocks and assigns them to files."""
    
    def __init__(
        self,
        code_map: Dict[str, List[str]],
        path_lookup: PathLookup,
        heading_mapper: HeadingMapper,
        strip_hints: bool
    ):
        self.code_map = code_map
        self.path_lookup = path_lookup
        self.heading_mapper = heading_mapper
        self.strip_hints = strip_hints
        self.warnings: List[str] = []
        self.unassigned_blocks: List[str] = []
        
    def process_fence_block(
        self,
        fence_info: str,
        fence_content: str,
        current_file: Optional[str] = None
    ) -> bool:
        """
        Process a fence block and assign it to a file.
        
        Args:
            fence_info: Fence info string (language tag)
            fence_content: Code block content
            current_file: Currently active file from heading
            
        Returns:
            True if successfully assigned
        """
        # Try current file first
        if current_file and current_file in self.code_map:
            return self._assign_to_file(current_file, fence_content, "current")
        
        # Try fence info inference
        if fence_info:
            return self._process_with_fence_info(fence_info, fence_content)
        
        # Try hint in content
        hint, _, has_hint = extract_hint_and_body(fence_content)
        if hint:
            return self._process_with_hint(hint, fence_content)
        
        # Fallback to unassigned
        self.unassigned_blocks.append(fence_content)
        self.warnings.append(f"⚠️ Could not assign fence block (no info/hint)")
        return False
    
    def _process_with_fence_info(self, fence_info: str, fence_content: str) -> bool:
        """Process fence block using fence info for inference."""
        try:
            candidates = infer_targets_from_fence_info(fence_info, list(self.code_map.keys()))
            
            # Try exact basename match first
            fence_basename = Path(fence_info).name
            basename_matches = self.path_lookup.find_by_basename(fence_basename)
            if len(basename_matches) == 1:
                return self._assign_to_file(basename_matches[0], fence_content, "exact_basename")
            
            # Single candidate match
            if len(candidates) == 1:
                return self._assign_to_file(candidates[0], fence_content, "inferred")
            
            # Multiple candidates
            if len(candidates) > 1:
                self.warnings.append(f"⚠️ Ambiguous fence info '{fence_info}' matches {candidates}")
                self.unassigned_blocks.append(fence_content)
                return True
            
        except Exception as e:
            self.warnings.append(f"⚠️ Failed to infer targets from fence info '{fence_info}': {e}")
            self.unassigned_blocks.append(fence_content)
            return True
        
        return False
    
    def _process_with_hint(self, hint: str, fence_content: str) -> bool:
        """Process fence block using hint in content."""
        # Try direct path match
        exact_match = self.path_lookup.find_by_exact_path(hint)
        if exact_match:
            return self._assign_to_file(exact_match, fence_content, "hint_exact")
        
        # Try partial matches
        partial_matches = self.path_lookup.find_by_partial_path(hint)
        if len(partial_matches) == 1:
            return self._assign_to_file(partial_matches[0], fence_content, "hint_partial")
        elif len(partial_matches) > 1:
            self.warnings.append(f"⚠️ Ambiguous hint '{hint}' matches {partial_matches}")
            self.unassigned_blocks.append(fence_content)
            return True
        
        return False
    
    def _assign_to_file(
        self, 
        target_file: str, 
        content: str, 
        match_type: str
    ) -> bool:
        """
        Assign content to a specific file.
        
        Args:
            target_file: Target file path
            content: Code block content
            match_type: Type of match for logging
            
        Returns:
            True if successfully assigned
        """
        if target_file not in self.code_map:
            return False
        
        hint, _, has_hint = extract_hint_and_body(content)
        processed_content, was_modified, original_hint = process_code_block_content(
            content, target_file, self.strip_hints, has_hint
        )
        
        if was_modified:
            if self.strip_hints and original_hint:
                self.warnings.append(f"ℹ️ Stripped hint '{original_hint}' from code block")
            elif original_hint:
                self.warnings.append(f"ℹ️ Replaced hint '{original_hint}' with '{target_file}'")
        
        # Check for duplicate hints
        if self.code_map[target_file]:
            last_block = self.code_map[target_file][-1]
            last_hint, _, last_has_hint = extract_hint_and_body(last_block)
            if (last_has_hint and has_hint and 
                are_strings_similar(last_hint, hint) and 
                not self.strip_hints):
                self.warnings.append(f"⚠️ File {target_file} had multiple code blocks with similar hints")
        
        # Add to code map
        self.code_map[target_file].append(processed_content)
        
        # Log assignment
        log_message = f"ℹ️ Assigned fence block ({match_type}) -> {target_file}"
        if original_hint and not self.strip_hints:
            log_message += f" (was: '{original_hint}')"
        self.warnings.append(log_message)
        
        return True

# ============================================================================
# Main Mapping Function
# ============================================================================

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
    
    # Initialize code map with valid files
    code_map: Dict[str, List[str]] = {}
    for file_path in tree_files:
        try:
            if is_probably_file(Path(file_path).name, files_always, dirs_always):
                code_map[file_path] = []
        except Exception as e:
            logging.warning(f"⚠️ Failed to process tree file {file_path}: {e}")
    
    # Initialize helper objects
    path_lookup = PathLookup(list(code_map.keys()))
    heading_mapper = HeadingMapper(path_lookup)
    fence_processor = FenceBlockProcessor(code_map, path_lookup, heading_mapper, strip_hints)
    
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
            
            # Handle headings
            if tok.type == "heading_open":
                inline = tokens[i + 1] if (i + 1) < n else None
                heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
                heading_clean = normalize_path_string(heading_text)
                heading_clean = clean_markdown_formatting(heading_clean)
                
                if heading_clean.lower() == "file structure":
                    current_file = None
                    current_heading = None
                    skip_next_fence_for_file_structure = True
                else:
                    current_file, current_heading, heading_warnings = heading_mapper.map_heading_to_file(
                        heading_text, heading_clean
                    )
                    fence_processor.warnings.extend(heading_warnings)
                
                i += 1
                continue
            
            # Handle fence blocks
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
                
                fence_processor.process_fence_block(fence_info, fence_content, current_file)
                i += 1
                continue
            
            # Handle paragraphs under headings as potential content
            if tok.type == "paragraph_open" and current_file and current_file in code_map:
                inline = tokens[i + 1] if (i + 1) < n else None
                para_text = inline.content.strip() if inline and inline.type == "inline" else ""
                if para_text:
                    # Avoid adding duplicate content
                    if not code_map[current_file] or code_map[current_file][-1] != para_text:
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
    
    logging.info(f"✅ Mapping complete: {len(code_map)} files, {len(fence_processor.unassigned_blocks)} unassigned blocks")
    
    return (
        code_map,
        fence_processor.unassigned_blocks,
        fence_processor.warnings,
        heading_mapper.file_to_heading
    )

# ============================================================================
# Debug and Analysis Utilities
# ============================================================================

def analyze_mapping_coverage(
    code_map: Dict[str, List[str]],
    tree_files: List[str]
) -> Dict[str, Any]:
    """
    Analyze how well files were mapped.
    
    Args:
        code_map: Resulting code map
        tree_files: Original tree files
        
    Returns:
        Dictionary with analysis metrics
    """
    total_tree_files = len(tree_files)
    mapped_files = len(code_map)
    files_with_content = sum(1 for blocks in code_map.values() if blocks)
    total_blocks = sum(len(blocks) for blocks in code_map.values())
    
    return {
        "total_tree_files": total_tree_files,
        "mapped_files": mapped_files,
        "files_with_content": files_with_content,
        "total_code_blocks": total_blocks,
        "coverage_percentage": (mapped_files / total_tree_files * 100) if total_tree_files > 0 else 0,
        "content_percentage": (files_with_content / mapped_files * 100) if mapped_files > 0 else 0,
    }

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
    debug_info: Dict[str, Any] = {
         "tokens_count": len(tokens),
         "tree_files_count": len(tree_files),
         "headings_found": sum(1 for t in tokens if t.type == "heading_open"),
         "fence_blocks_found": sum(1 for t in tokens if t.type == "fence"),
     }
    
    # Run mapping
    code_map, unassigned, warnings, heading_map = map_headings_to_files(
        tokens, tree_files, files_always, dirs_always
    )
    
    # Add results to debug info
    debug_info.update({
        "mapped_files_count": len(code_map),
        "unassigned_blocks_count": len(unassigned),
        "warnings_count": len(warnings),
        "heading_map_entries": len(heading_map),
        "analysis": analyze_mapping_coverage(code_map, tree_files)
    })
    
    return debug_info

# ============================================================================
# Batch Processing Utilities
# ============================================================================

def batch_process_markdown_files(
    markdown_files: List[Path],
    tree_files_provider,  # Callable that returns tree files for a markdown file
    files_always: Set[str],
    dirs_always: Set[str],
    strip_hints: bool = False
) -> Dict[Path, Dict[str, Any]]:
    """
    Process multiple markdown files in batch.
    
    Args:
        markdown_files: List of markdown file paths
        tree_files_provider: Function that returns tree files for a given markdown file
        files_always: Set of names to treat as files
        dirs_always: Set of names to treat as directories
        strip_hints: Whether to strip hints
        
    Returns:
        Dictionary mapping markdown files to their processing results
    """
    results = {}
    
    for md_file in markdown_files:
        try:
            # Parse markdown and get tokens
            # (You'll need to implement this based on your markdown parser)
            tokens: List[Token] = []  # Placeholder - implement based on your parser
            
            # Get tree files for this markdown
            tree_files = tree_files_provider(md_file)
            
            # Process mapping
            code_map, unassigned, warnings, heading_map = map_headings_to_files(
                tokens, tree_files, files_always, dirs_always, strip_hints
            )
            
            results[md_file] = {
                "code_map": code_map,
                "unassigned": unassigned,
                "warnings": warnings,
                "heading_map": heading_map,
                "success": True
            }
            
        except Exception as e:
            logging.error(f"❌ Failed to process {md_file}: {e}")
            results[md_file] = {
                "success": False,
                "error": str(e)
            }
    
    return results

# ============================================================================
# Helper Functions for External Use
# ============================================================================

def get_mapped_files_for_heading(
    heading_text: str,
    tree_files: List[str],
    files_always: Set[str],
    dirs_always: Set[str]
) -> List[str]:
    """
    Get potential file matches for a heading without full processing.
    
    Args:
        heading_text: Heading text to match
        tree_files: Available file paths
        files_always: Set of names to treat as files
        dirs_always: Set of names to treat as directories
        
    Returns:
        List of potential file matches
    """
    # Filter to valid files
    valid_files = []
    for file_path in tree_files:
        try:
            if is_probably_file(Path(file_path).name, files_always, dirs_always):
                valid_files.append(file_path)
        except Exception:
            continue
    
    # Clean and normalize heading
    heading_clean = normalize_path_string(heading_text)
    heading_clean = clean_markdown_formatting(heading_clean)
    
    # Create lookup and find matches
    path_lookup = PathLookup(valid_files)
    
    # Try multiple strategies
    matches = []
    
    # Exact match
    exact_match = path_lookup.find_by_exact_path(heading_clean)
    if exact_match:
        matches.append(exact_match)
    
    # Partial matches
    matches.extend(path_lookup.find_by_partial_path(heading_clean))
    
    # Basename match
    try:
        basename = Path(heading_clean).name
        matches.extend(path_lookup.find_by_basename(basename))
    except Exception:
        pass
    
    # Fuzzy matches
    matches.extend(path_lookup.find_by_fuzzy_match(heading_clean))
    
    # Remove duplicates and return
    return list(dict.fromkeys(matches))  # Preserve order while deduplicating