# utils/extract_file_structure_block/extract_file_structure_block.py
from typing import List, Optional, Tuple
from markdown_it.token import Token
import re
import logging
from functools import lru_cache

# Pre-compile regex patterns for performance
FILE_STRUCTURE_PATTERN = re.compile(
    r"(?is)(?:^|\n)##+\s*.*structure.*?\s*(?:\n+)?\`\`\`(?:\w+)?\s*\n([\s\S]*?)\n\`\`\`",
    re.IGNORECASE
)

FILE_STRUCTURE_PATTERN_ALT = re.compile(
    r"(?is)(?:^|\n)(?:#+\s*.*structure|File\s+Structure|Folder\s+Structure).*?\n\`\`\`(?:\w+)?\s*\n([\s\S]*?)\n\`\`\`",
    re.IGNORECASE
)

TREE_LIKE_PATTERN = re.compile(
    r"\`\`\`(?:\w+)?\s*\n((?:[├└│─\s\w\.\-/]+\n)+)\`\`\`",
    re.IGNORECASE
)

STRUCTURE_KEYWORDS = {"structure", "file structure", "folder structure", "directory structure", "project structure"}

def is_structure_heading(content: str) -> bool:
    if not content:
        return False
    
    content_lower = content.lower().strip()
    
    for keyword in STRUCTURE_KEYWORDS:
        if keyword in content_lower:
            return True
    
    words = content_lower.split()
    if len(words) >= 2 and "structure" in words:
        return True
    
    if "structure" in content_lower and len(content_lower) < 50:
        return True
    
    return False

def find_structure_heading_index(tokens: List[Token]) -> Optional[int]:
    for i, token in enumerate(tokens):
        if (token.type == "heading_open" and 
            i + 1 < len(tokens) and 
            tokens[i + 1].type == "inline"):
            
            heading_content = tokens[i + 1].content
            if is_structure_heading(heading_content):
                return i
    
    return None

def extract_code_block_after_heading(tokens: List[Token], heading_index: int) -> Optional[str]:
    start_index = heading_index + 2
    
    for j in range(start_index, len(tokens)):
        current_token = tokens[j]
        
        if current_token.type == "heading_open":
            try:
                current_level = int(tokens[heading_index].tag[1])
                new_level = int(current_token.tag[1])
                if new_level <= current_level:
                    break
            except (ValueError, IndexError):
                break
            
        if current_token.type == "fence":
            return current_token.content
            
    return None

def fallback_regex_search(md_text: str) -> Optional[str]:
    try:
        # Primary pattern
        match = FILE_STRUCTURE_PATTERN.search(md_text)
        if match:
            content = match.group(1)
            return content
        
        # Alternative pattern
        match = FILE_STRUCTURE_PATTERN_ALT.search(md_text)
        if match:
            content = match.group(1)
            return content
        
        # Tree-like pattern
        match = TREE_LIKE_PATTERN.search(md_text)
        if match:
            content = match.group(1)
            lines = content.splitlines()
            tree_indicators = sum(1 for line in lines[:10] if any(indicator in line for indicator in ["/", "│", "├", "└", "──"]))
            if tree_indicators >= 2:
                return content
        
    except Exception as e:
        logging.warning(f"⚠️ Regex fallback search failed: {e}")
    
    return None

def validate_structure_content(content: Optional[str]) -> Optional[str]:
    if not content:
        return None
    
    content = content.strip()
    
    if not content:
        logging.warning("⚠️ Extracted file structure content is empty")
        return None
    
    lines = content.splitlines()
    if len(lines) < 1:
        logging.warning("⚠️ File structure content has no lines")
        return None
    
    structure_indicators = 0
    file_like_indicators = 0
    
    for line in lines[:10]:
        line_clean = line.strip()
        
        if any(indicator in line_clean for indicator in ["│", "├", "└", "──"]):
            structure_indicators += 1
        
        if any(indicator in line_clean for indicator in ["/", ".json", ".js", ".py", ".html", ".css", ".md"]):
            file_like_indicators += 1
        
        if line_clean.endswith('/') and len(line_clean) > 1:
            structure_indicators += 1
    
    if structure_indicators == 0 and file_like_indicators < 2:
        logging.warning("⚠️ Extracted content doesn't look like a file structure")
    
    logging.debug(f"✅ Validated file structure: {len(lines)} lines")
    return content

def extract_file_structure_block(md_text: str, tokens: List[Token]) -> Optional[str]:
    if not tokens:
        logging.warning("⚠️ Empty tokens list provided")
        return fallback_regex_search(md_text)
    
    if not md_text or not isinstance(md_text, str):
        logging.warning("⚠️ Invalid markdown text provided")
        return None
    
    try:
        # Method 1: Token-based extraction
        heading_index = find_structure_heading_index(tokens)
        
        if heading_index is not None:
            content = extract_code_block_after_heading(tokens, heading_index)
            
            if content:
                validated_content = validate_structure_content(content)
                if validated_content:
                    return validated_content
        
        # Method 2: Regex fallback
        regex_content = fallback_regex_search(md_text)
        if regex_content:
            validated_content = validate_structure_content(regex_content)
            if validated_content:
                return validated_content
        
        # Method 3: Generic code block search
        for token in tokens:
            if token.type == "fence":
                content = token.content.strip()
                if content:
                    lines = content.splitlines()
                    if len(lines) >= 3:
                        structure_indicators = sum(
                            1 for line in lines[:5] 
                            if any(indicator in line for indicator in ["/", "│", "├", "└", "──"])
                        )
                        if structure_indicators >= 2:
                            validated_content = validate_structure_content(content)
                            if validated_content:
                                return validated_content
        
        logging.warning("❌ Could not find file structure block")
        return None
        
    except Exception as e:
        logging.error(f"❌ Unexpected error extracting file structure: {e}")
        try:
            return fallback_regex_search(md_text)
        except Exception as final_error:
            logging.error(f"❌ Final fallback also failed: {final_error}")
            return None

def debug_file_structure_extraction(md_text: str, tokens: List[Token]) -> dict:
    debug_info = {
        "tokens_count": len(tokens),
        "has_structure_heading": False,
        "heading_content": None,
        "code_blocks_found": 0,
        "extraction_method": None,
        "success": False
    }
    
    debug_info["code_blocks_found"] = sum(1 for token in tokens if token.type == "fence")
    
    heading_index = find_structure_heading_index(tokens)
    if heading_index is not None:
        debug_info["has_structure_heading"] = True
        debug_info["heading_content"] = tokens[heading_index + 1].content if heading_index + 1 < len(tokens) else None
    
    result = extract_file_structure_block(md_text, tokens)
    debug_info["success"] = result is not None
    debug_info["result_length"] = len(result) if result else 0
    
    return debug_info