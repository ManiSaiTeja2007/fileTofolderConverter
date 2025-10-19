from markdown_it import MarkdownIt
from pathlib import Path
from typing import Tuple, List, Optional
from markdown_it.token import Token
import re
import logging
from functools import lru_cache

# Compile regex patterns once for performance
CODE_BLOCK_PATTERN = re.compile(r'```[\w\s]*\n([\s\S]*?)\n```', re.DOTALL)
XAI_ARTIFACT_PATTERN = re.compile(
    r'(?<!#)^[ \t]*<xaiArtifact.*?title="([^"]*)".*?contentType="([^"]*)">([\s\S]*?)</xaiArtifact>',
    re.IGNORECASE | re.MULTILINE | re.DOTALL
)
DOCUMENT_TAG_PATTERN = re.compile(r'<DOCUMENT[^>]*>[\s\S]*?</DOCUMENT>', re.DOTALL | re.IGNORECASE)

@lru_cache(maxsize=10)
def get_markdown_parser() -> MarkdownIt:
    """Get cached Markdown parser instance."""
    return MarkdownIt("commonmark")

def safe_read_file(path: Path, max_size: int = 10 * 1024 * 1024) -> Optional[str]:
    """
    Safely read file with size limits and encoding handling.
    
    Args:
        path: Path to the file
        max_size: Maximum file size in bytes (default: 10MB)
    
    Returns:
        File content or None if failed
    """
    try:
        # Check file size first
        file_size = path.stat().st_size
        if file_size > max_size:
            logging.error(f"❌ File too large: {path} ({file_size} bytes > {max_size} bytes limit)")
            return None
        
        # Read with encoding fallback
        content = path.read_text(encoding="utf-8", errors="replace")
        return content
        
    except FileNotFoundError:
        logging.error(f"❌ File not found: {path}")
        return None
    except PermissionError:
        logging.error(f"❌ Permission denied: {path}")
        return None
    except Exception as e:
        logging.error(f"❌ Failed to read file {path}: {e}")
        return None

def preprocess_code_blocks(content: str) -> str:
    """
    Preprocess code blocks to escape <xaiArtifact> tags.
    
    Args:
        content: Original markdown content
        
    Returns:
        Preprocessed content with escaped tags in code blocks
    """
    def escape_artifacts_in_code(match):
        code_content = match.group(1)
        if "<xaiArtifact" in code_content.lower():
            # Extract language from code fence
            fence_line = match.group(0).splitlines()[0]
            lang = fence_line.strip()[3:]  # Remove ``` and get language
            escaped_content = code_content.replace("<xaiArtifact", "&lt;xaiArtifact").replace("</xaiArtifact>", "&lt;/xaiArtifact>")
            return f"```{lang}\n{escaped_content}\n```"
        return match.group(0)  # Return unchanged if no artifacts found
    
    try:
        return CODE_BLOCK_PATTERN.sub(escape_artifacts_in_code, content)
    except Exception as e:
        logging.warning(f"⚠️ Failed to preprocess code blocks: {e}")
        return content  # Return original content on error

def convert_xai_artifacts(content: str) -> str:
    """
    Convert <xaiArtifact> tags to Markdown headings and code blocks.
    
    Args:
        content: Markdown content with xaiArtifact tags
        
    Returns:
        Content with converted artifacts
    """
    def artifact_to_markdown(match):
        title = match.group(1) or "Untitled"
        content_type = match.group(2) or "text/plain"
        code_content = match.group(3) or ""
        
        # Validate inputs
        if not title.strip():
            logging.warning("⚠️ Empty title in <xaiArtifact> tag")
            title = "Untitled"
        
        # Extract language from content type
        lang = "text"
        if "/" in content_type:
            lang = content_type.split("/")[-1]
            # Clean up common language names
            if lang in ["javascript", "x-javascript"]:
                lang = "javascript"
            elif lang in ["python", "x-python"]:
                lang = "python"
            elif lang == "plain":
                lang = "text"
        
        # Clean up code content
        code_content = code_content.strip()
        if not code_content:
            logging.debug(f"Empty content in artifact: {title}")
        
        return f"\n## {title}\n```{lang}\n{code_content}\n```"
    
    try:
        return XAI_ARTIFACT_PATTERN.sub(artifact_to_markdown, content)
    except Exception as e:
        logging.warning(f"⚠️ Failed to process <xaiArtifact> tags: {e}")
        return content

def strip_document_tags(content: str) -> str:
    """
    Remove <DOCUMENT> tags from content.
    
    Args:
        content: Markdown content
        
    Returns:
        Content with document tags removed
    """
    try:
        return DOCUMENT_TAG_PATTERN.sub('', content)
    except Exception as e:
        logging.warning(f"⚠️ Failed to strip <DOCUMENT> tags: {e}")
        return content

def parse_markdown_tokens(content: str) -> Optional[List[Token]]:
    """
    Parse markdown content into tokens.
    
    Args:
        content: Markdown content to parse
        
    Returns:
        List of tokens or None if parsing failed
    """
    try:
        parser = get_markdown_parser()
        tokens = parser.parse(content)
        return tokens
    except Exception as e:
        logging.error(f"❌ Failed to parse Markdown content: {e}")
        return None

def load_markdown(path: Path) -> Tuple[str, List[Token]]:
    """
    Load and parse a Markdown file, converting <xaiArtifact> tags to headings and code blocks,
    while ignoring tags in # comments or within code fences.
    
    Args:
        path: Path to the Markdown file.
        
    Returns:
        Tuple of (text, tokens): The preprocessed text and parsed Markdown tokens.
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is too large or unreadable
        Exception: For other critical failures
    """
    # Validate input
    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {path}")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    
    # Read file safely
    content = safe_read_file(path)
    if content is None:
        raise ValueError(f"Failed to read file: {path}")
    
    # Log file stats for debugging
    file_size = path.stat().st_size
    line_count = content.count('\n') + 1
    logging.debug(f"📖 Loading markdown: {path} ({file_size} bytes, {line_count} lines)")
    
    # Preprocessing pipeline
    try:
        # Step 1: Preprocess code blocks (escape artifacts in code)
        processed_content = preprocess_code_blocks(content)
        
        # Step 2: Convert xaiArtifact tags to markdown
        processed_content = convert_xai_artifacts(processed_content)
        
        # Step 3: Remove document tags
        processed_content = strip_document_tags(processed_content)
        
        # Step 4: Parse to tokens
        tokens = parse_markdown_tokens(processed_content)
        if tokens is None:
            raise ValueError("Failed to parse markdown tokens")
        
        logging.debug(f"✅ Successfully parsed {path}: {len(tokens)} tokens generated")
        return processed_content, tokens
        
    except Exception as e:
        logging.error(f"❌ Critical error processing {path}: {e}")
        # Fallback: try to parse original content without preprocessing
        logging.info("🔄 Attempting fallback parsing without preprocessing...")
        try:
            tokens = parse_markdown_tokens(content)
            if tokens:
                logging.warning("⚠️ Using fallback parsing (some features may not work)")
                return content, tokens
        except Exception as fallback_error:
            logging.error(f"❌ Fallback parsing also failed: {fallback_error}")
        
        raise Exception(f"Failed to process markdown file {path}: {e}")

# Test function for development
def test_load_markdown():
    """Test function for development and debugging."""
    test_file = Path("test.md")
    if test_file.exists():
        try:
            content, tokens = load_markdown(test_file)
            print(f"✅ Test successful: {len(tokens)} tokens")
            return True
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False
    else:
        print("⚠️ Test file not found: test.md")
        return False

if __name__ == "__main__":
    # Enable debug logging for testing
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    test_load_markdown()