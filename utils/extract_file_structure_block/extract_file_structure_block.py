# utils/extract_file_structure_block/extract_file_structure_block.py
from typing import List, Optional
from markdown_it.token import Token
import re

def extract_file_structure_block(md_text: str, tokens: List[Token]) -> Optional[str]:
    """
    Extract the 'File Structure' block from Markdown tokens, handling nested code blocks.
    Searches for a heading containing 'structure' followed by a fenced code block.
    Args:
        md_text: Raw Markdown text.
        tokens: Parsed Markdown tokens.
    Returns:
        Content of the file structure block, or None if not found.
    """
    # Search for heading with 'structure' (case-insensitive)
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and i + 1 < len(tokens) and tokens[i + 1].type == "inline":
            if "structure" in tokens[i + 1].content.lower():
                # Look for the next fenced code block
                j = i + 2
                while j < len(tokens):
                    if tokens[j].type == "fence":
                        return tokens[j].content
                    if tokens[j].type == "heading_open":
                        break  # Stop at next heading
                    j += 1

    # Fallback to regex if token parsing fails
    m = re.search(
        r"(?is)(?:^|\n)##+\s*.*structure.*\s*(?:\n+)(```(?:text)?\n([\s\S]*?)\n```)",
        md_text,
    )
    if m:
        return m.group(2)
    
    return None