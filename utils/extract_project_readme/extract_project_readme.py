from typing import List, Set, Optional
from pathlib import Path
from markdown_it.token import Token
import logging

from utils.is_probably_file.is_probably_file import is_probably_file

def extract_file_names(tree_entries: List[str], files_always: Optional[Set[str]] = None, dirs_always: Optional[Set[str]] = None) -> Set[str]:
    """
    Extract file names from tree entries, excluding directories.
    
    Args:
        tree_entries: List of file and directory paths
        files_always: Set of names to always treat as files
        dirs_always: Set of names to always treat as directories
        
    Returns:
        Set of file names
    """
    file_names = set()
    
    for entry in tree_entries:
        path = Path(entry)
        if is_probably_file(path.name, files_always or set(), dirs_always or set()):
            file_names.add(path.name)
    
    return file_names

def should_skip_heading(heading_text: str, file_names: Set[str]) -> bool:
    """
    Determine if a heading should be skipped based on content.
    
    Args:
        heading_text: The heading content
        file_names: Set of file names to exclude
        
    Returns:
        True if heading should be skipped
    """
    if not heading_text.strip():
        return False
    
    heading_path = Path(heading_text)
    
    # Skip if heading matches a file name
    if heading_path.name in file_names:
        logging.debug(f"📄 Skipping file-specific heading: {heading_text}")
        return True
    
    # Skip file structure sections
    if heading_text.strip().lower() in {"file structure", "folder structure", "directory structure", "project structure"}:
        logging.debug(f"📁 Skipping structure heading: {heading_text}")
        return True
    
    return False

def extract_heading_content(tokens: List[Token], start_index: int) -> List[str]:
    """
    Extract content under a heading until the next heading.
    
    Args:
        tokens: List of markdown tokens
        start_index: Starting index after the heading
        
    Returns:
        List of content lines
    """
    content_lines = []
    i = start_index
    n = len(tokens)
    
    while i < n and tokens[i].type != "heading_open":
        token = tokens[i]
        
        if token.type == "inline":
            content_lines.append(token.content)
            
        elif token.type == "fence":
            # Handle code blocks
            info = getattr(token, "info", "") or ""
            code_content = token.content.rstrip()
            fence_block = f"```{info}\n{code_content}\n```"
            content_lines.append(fence_block)
            
        elif token.type == "paragraph_open":
            # Handle paragraphs
            if i + 1 < n and tokens[i + 1].type == "inline":
                content_lines.append(tokens[i + 1].content)
            # Skip to paragraph close
            j = i + 1
            while j < n and tokens[j].type != "paragraph_close":
                j += 1
            i = j
            
        elif token.type in {"bullet_list_open", "ordered_list_open"}:
            # Handle lists
            j = i
            while j < n and tokens[j].type not in {"bullet_list_close", "ordered_list_close"}:
                if tokens[j].type == "inline":
                    content_lines.append(f"• {tokens[j].content}")
                j += 1
            i = j
            
        elif token.type == "blockquote_open":
            # Handle blockquotes
            if i + 1 < n and tokens[i + 1].type == "inline":
                content_lines.append(f"> {tokens[i + 1].content}")
            j = i + 1
            while j < n and tokens[j].type != "blockquote_close":
                j += 1
            i = j
        
        i += 1
    
    return content_lines

def process_heading_section(tokens: List[Token], i: int, file_names: Set[str]) -> tuple[Optional[str], int]:
    """
    Process a heading section and extract its content if not skipped.
    
    Args:
        tokens: List of markdown tokens
        i: Current token index
        file_names: Set of file names to exclude
        
    Returns:
        Tuple of (section_content, new_index)
    """
    if i + 1 >= len(tokens):
        return None, i + 1
    
    inline_token = tokens[i + 1]
    if inline_token.type != "inline":
        return None, i + 1
    
    heading_text = inline_token.content.strip()
    
    # Check if we should skip this heading
    if should_skip_heading(heading_text, file_names):
        return None, i + 2  # Skip heading_open and inline
    
    # Format heading level
    heading_level = ""
    if tokens[i].tag.startswith('h'):
        try:
            level = int(tokens[i].tag[1])
            heading_level = "#" * level + " "
        except (ValueError, IndexError):
            heading_level = "# "
    
    if not heading_text.startswith("#"):
        heading_line = f"{heading_level}{heading_text}"
    else:
        heading_line = heading_text
    
    # Extract content under this heading
    content_lines = extract_heading_content(tokens, i + 2)
    
    if not content_lines:
        logging.debug(f"📝 Empty section under heading: {heading_text}")
        return heading_line, i + 2
    
    # Combine heading and content
    section_content = "\n\n".join([heading_line] + content_lines).strip()
    logging.debug(f"📝 Extracted section: {heading_text} ({len(content_lines)} content lines)")
    
    return section_content, i + 2

def validate_extracted_readme(content: str) -> str:
    """
    Validate and clean the extracted README content.
    
    Args:
        content: Raw extracted content
        
    Returns:
        Cleaned and validated content
    """
    if not content:
        return ""
    
    content = content.strip()
    
    # Remove excessive blank lines
    lines = content.split('\n')
    cleaned_lines = []
    prev_was_blank = False
    
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_was_blank:
            continue
        cleaned_lines.append(line)
        prev_was_blank = is_blank
    
    cleaned_content = '\n'.join(cleaned_lines)
    
    # Ensure it ends with a newline
    if cleaned_content and not cleaned_content.endswith('\n'):
        cleaned_content += '\n'
    
    return cleaned_content

def extract_project_readme(tokens: List[Token], tree_entries: List[str], 
                          files_always: Optional[Set[str]] = None, 
                          dirs_always: Optional[Set[str]] = None) -> str:
    """
    Extract project README content from markdown tokens, excluding file-specific sections.
    
    Args:
        tokens: Parsed markdown tokens
        tree_entries: List of file paths from the project structure
        files_always: Set of names to always treat as files
        dirs_always: Set of names to always treat as directories
        
    Returns:
        Extracted README content as a string
    """
    # Input validation
    if not tokens:
        logging.warning("⚠️ No tokens provided for README extraction")
        return ""
    
    if not tree_entries:
        logging.warning("⚠️ No tree entries provided for README extraction")
    
    try:
        # Extract file names to exclude
        file_names = extract_file_names(tree_entries, files_always, dirs_always)
        logging.debug(f"📋 Excluding {len(file_names)} file-specific sections")
        
        out_sections: List[str] = []
        i = 0
        n = len(tokens)
        
        while i < n:
            token = tokens[i]
            
            if token.type == "heading_open":
                section_content, new_index = process_heading_section(tokens, i, file_names)
                if section_content:
                    out_sections.append(section_content)
                i = new_index
            else:
                i += 1
        
        if not out_sections:
            logging.warning("⚠️ No README content extracted")
            return ""
        
        # Combine all sections
        combined_content = "\n\n".join(out_sections)
        validated_content = validate_extracted_readme(combined_content)
        
        logging.info(f"✅ Extracted README: {len(out_sections)} sections, {len(validated_content)} characters")
        return validated_content
        
    except Exception as e:
        logging.error(f"❌ Error extracting README: {e}")
        return ""

# Utility function for debugging
def debug_readme_extraction(tokens: List[Token], tree_entries: List[str]) -> dict:
    """
    Debug function to analyze README extraction process.
    
    Args:
        tokens: Parsed markdown tokens
        tree_entries: List of file paths
        
    Returns:
        Dictionary with debug information
    """
    debug_info = {
        "tokens_count": len(tokens),
        "tree_entries_count": len(tree_entries),
        "file_names_found": 0,
        "headings_processed": 0,
        "sections_extracted": 0,
        "total_content_length": 0
    }
    
    file_names = extract_file_names(tree_entries)
    debug_info["file_names_found"] = len(file_names)
    
    # Count headings
    headings = [tokens[i + 1].content for i, t in enumerate(tokens) 
                if t.type == "heading_open" and i + 1 < len(tokens) and tokens[i + 1].type == "inline"]
    debug_info["headings_processed"] = len(headings)
    
    # Extract content
    content = extract_project_readme(tokens, tree_entries)
    debug_info["sections_extracted"] = content.count('# ') if content else 0
    debug_info["total_content_length"] = len(content) if content else 0
    
    return debug_info