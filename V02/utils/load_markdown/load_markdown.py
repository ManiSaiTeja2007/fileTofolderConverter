from markdown_it import MarkdownIt
from pathlib import Path
from typing import Tuple, List
from markdown_it.token import Token

def load_markdown(path: Path) -> Tuple[str, List[Token]]:
    md = MarkdownIt("commonmark")
    txt = path.read_text(encoding="utf-8")
    tokens = md.parse(txt)
    return txt, tokens