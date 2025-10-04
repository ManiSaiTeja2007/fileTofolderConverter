from markdown_it import MarkdownIt
from pathlib import Path
from typing import Tuple, List
from markdown_it.token import Token
import re
import logging

def load_markdown(path: Path) -> Tuple[str, List[Token]]:
    """
    Load and parse a Markdown file, converting <xaiArtifact> tags to headings and code blocks,
    while ignoring tags in # comments or within code fences.
    Args:
        path: Path to the Markdown file.
    Returns:
        Tuple of (text, tokens): The preprocessed text and parsed Markdown tokens.
    """
    try:
        md = MarkdownIt("commonmark")
        txt = path.read_text(encoding="utf-8", errors="replace")

        # Preprocess code blocks to escape <xaiArtifact> tags
        def preprocess_code_blocks(match):
            content = match.group(1)
            if "<xaiArtifact" in content.lower():
                logging.debug(f"Ignoring <xaiArtifact> in code block: {content[:50]}...")
                content = content.replace("<xaiArtifact", "&lt;xaiArtifact").replace("</xaiArtifact>", "&lt;/xaiArtifact>")
            return f"```{match.group(0).splitlines()[0].strip()[3:]}\n{content}\n```"

        try:
            txt = re.sub(r'```[\w\s]*\n([\s\S]*?)\n```', preprocess_code_blocks, txt, flags=re.DOTALL)
        except Exception as e:
            logging.warning(f"⚠️ Failed to preprocess code blocks: {e}. Proceeding with original text.")

        # Convert <xaiArtifact> tags to Markdown headings and code blocks, ignoring those after #
        def replace_artifact(match):
            title = match.group(1)
            content_type = match.group(2)
            code = match.group(3)
            if not title or not content_type:
                logging.warning(f"⚠️ Malformed <xaiArtifact> tag: title='{title}', contentType='{content_type}'")
                return ""
            lang = content_type.split("/")[-1] if content_type else "text"
            return f"\n## {title}\n```{lang}\n{code}\n```"

        try:
            pattern = re.compile(
                r'(?<!#)^[ \t]*<xaiArtifact.*?title="([^"]*)".*?contentType="([^"]*)">([\s\S]*?)</xaiArtifact>',
                re.IGNORECASE | re.MULTILINE | re.DOTALL
            )
            txt = pattern.sub(replace_artifact, txt)
        except Exception as e:
            logging.warning(f"⚠️ Failed to process <xaiArtifact> tags: {e}. Proceeding with preprocessed text.")

        # Strip <DOCUMENT> tags
        try:
            txt = re.sub(r'<DOCUMENT[^>]*>[\s\S]*?</DOCUMENT>', '', txt, flags=re.DOTALL | re.IGNORECASE)
        except Exception as e:
            logging.warning(f"⚠️ Failed to strip <DOCUMENT> tags: {e}. Proceeding with preprocessed text.")

        tokens = md.parse(txt)
        return txt, tokens

    except FileNotFoundError:
        logging.error(f"❌ File not found: {path}")
        raise
    except UnicodeDecodeError:
        logging.error(f"❌ Failed to decode file {path}: Invalid encoding")
        raise
    except Exception as e:
        logging.error(f"❌ Failed to parse Markdown {path}: {e}")
        raise