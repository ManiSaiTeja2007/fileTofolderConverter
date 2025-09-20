from typing import List, Optional
from markdown_it.token import Token
import re

def extract_file_structure_block(md_text: str, tokens: List[Token]) -> Optional[str]:
    # Additional stripping for safety
    md_text = re.sub(r'<xaiArtifact[^>]*>[\s\S]*?</xaiArtifact>', '', md_text, flags=re.DOTALL | re.IGNORECASE)
    md_text = re.sub(r'<DOCUMENT[^>]*>[\s\S]*?</DOCUMENT>', '', md_text, flags=re.DOTALL | re.IGNORECASE)
    # Broaden search for headings containing "structure"
    for i, tok in enumerate(tokens):
        if tok.type == "inline" and "structure" in tok.content.lower():
            j = i + 1
            while j < len(tokens):
                if tokens[j].type in ("fence", "code_block"):
                    return tokens[j].content
                if tokens[j].type == "heading_open":
                    break
                j += 1
    # Fallback regex with broader heading match
    m = re.search(
        r"(?is)(?:^|\n)##+\s*.*structure.*\s*(?:\n+)(```(?:[\s\S]*?)```|(?:[\s\S]*?)(?=\n##|\Z))",
        md_text,
    )
    if m:
        block = m.group(1)
        if block.startswith("```"):
            return re.sub(r"^```[^\n]*\n([\s\S]*?)\n```$", r"\1", block, flags=re.I)
        return block
    return None
