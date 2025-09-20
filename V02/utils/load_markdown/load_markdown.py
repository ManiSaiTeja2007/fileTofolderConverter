from markdown_it import MarkdownIt
from pathlib import Path
from typing import Tuple, List
from markdown_it.token import Token
import re

def load_markdown(path: Path) -> Tuple[str, List[Token]]:
    md = MarkdownIt("commonmark")
    txt = path.read_text(encoding="utf-8")
    # Preprocess to convert <xaiArtifact> to standard Markdown headings and code blocks
    # Find all <xaiArtifact title="path" contentType="type">code</xaiArtifact>
    def replace_artifact(match):
        title = match.group(1)
        content_type = match.group(2)
        code = match.group(3)
        lang = content_type.split("/")[-1] if content_type else "text"
        return f"\n## {title}\n```{lang}\n{code}\n```"

    txt = re.sub(r'<xaiArtifact.*?title="([^"]*)".*?contentType="([^"]*)">([\s\S]*?)</xaiArtifact>', replace_artifact, txt, flags=re.DOTALL | re.IGNORECASE)
    # Strip <DOCUMENT> tags
    txt = re.sub(r'<DOCUMENT[^>]*>[\s\S]*?</DOCUMENT>', '', txt, flags=re.DOTALL | re.IGNORECASE)
    tokens = md.parse(txt)
    return txt, tokens