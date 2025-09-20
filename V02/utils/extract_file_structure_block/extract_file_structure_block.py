from typing import List, Optional
from markdown_it.token import Token
import re

def extract_file_structure_block(md_text: str, tokens: List[Token]) -> Optional[str]:
    for i, tok in enumerate(tokens):
        if tok.type == "inline" and "file structure" in tok.content.lower():
            j = i + 1
            while j < len(tokens):
                if tokens[j].type in ("fence", "code_block"):
                    return tokens[j].content
                if tokens[j].type == "heading_open":
                    break
                j += 1
    m = re.search(
        r"(?is)(?:^|\n)##+\s*File Structure\s*(?:\n+)(```(?:[\s\S]*?)```|(?:[\s\S]*?)(?=\n##|\Z))",
        md_text,
    )
    if m:
        block = m.group(1)
        if block.startswith("```"):
            return re.sub(r"^```[^\n]*\n([\s\S]*?)\n```$", r"\1", block, flags=re.I)
        return block
    return None