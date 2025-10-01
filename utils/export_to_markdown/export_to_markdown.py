from pathlib import Path
from typing import List, Tuple
import re
import logging
import fnmatch

from utils.verify_output.verify_output import verify_output  # For comparison

# Default ignore patterns for common build artifacts and Node.js files
DEFAULT_IGNORE_PATTERNS = [
    "node_modules/**",
    "package-lock.json",
    "yarn.lock",
    ".npmrc",
    "dist/**",
    "build/**",
    ".venv/**",
    "venv/**",
    ".env",
    ".DS_Store",
    "__pycache__/**",
    "*.pyc",
]

def export_to_markdown(folder: Path, md_path: Path):
    lines = ["# Exported Project", "## File Structure", "```text"]
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if p.is_dir():
            lines.append(str(rel) + "/")
        else:
            lines.append(str(rel))
    lines.append("```")
    for p in sorted(folder.rglob("*")):
        rel = p.relative_to(folder)
        if p.is_file():
            lines.append(f"\n## {rel}")
            ext = p.suffix.lstrip(".")
            lang = "text" if not ext else ext
            content = p.read_text(encoding="utf-8")
            lines.append(f"```{lang}\n{content}\n```")
    md_path.write_text("\n".join(lines), encoding="utf-8")

from typing import Optional

def folder_to_markdown(folder: Path, output_md: Path, compare: bool = True, user_ignore: Optional[List[str]] = None) -> Tuple[List[str], List[str]]:
    """
    Convert a folder to a Markdown file with file structure and contents, respecting .gitignore and default ignore patterns.
    The output MD is formatted to be reproducible (parsable back to folder).
    Escapes backticks in file contents to prevent parser confusion.
    Args:
        folder: Path to the input folder.
        output_md: Path to the output Markdown file.
        compare: Whether to compare generated structure against folder (default: True).
        user_ignore: List of user-provided ignore patterns from --ignore flag.
    Returns:
        Tuple of (file_list, warnings): List of files written to MD, and any warnings.
    """
    warnings: List[str] = []
    file_list: List[str] = []
    
    # Combine default and user-provided ignore patterns
    ignore_globs = DEFAULT_IGNORE_PATTERNS[:]
    if user_ignore:
        ignore_globs.extend(user_ignore)
    
    # Parse .gitignore if present, supporting basic negation with "!"
    gitignore_path = folder / ".gitignore"
    gitignore_ignores = []  # Positive ignores
    gitignore_unignores = []  # Negations like "!file.txt"
    if gitignore_path.exists():
        try:
            with gitignore_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if line.startswith("!"):
                            gitignore_unignores.append(line[1:].rstrip("/"))  # Strip "!" and trailing /
                        else:
                            gitignore_ignores.append(line.rstrip("/"))  # Strip trailing / for normalization
        except Exception as e:
            warnings.append(f"Failed to parse .gitignore: {str(e)}")
            logging.warning(f"Failed to parse .gitignore: {str(e)}")
    
    # Build full list of ignore globs (user/default + .gitignore ignores)
    ignore_globs.extend(gitignore_ignores)
    
    # Function to check if a path should be ignored
    def is_ignored(rel_path: str) -> bool:
        # Normalize rel_path (no leading /, use posix)
        rel_path = rel_path.lstrip("/").replace("\\", "/")
        
        # Check un-ignores first (negations override)
        for unignore in gitignore_unignores:
            if fnmatch.fnmatch(rel_path, unignore) or fnmatch.fnmatch(rel_path, unignore + "/**"):
                logging.debug(f"Un-ignoring path due to '!{unignore}': {rel_path}")
                return False
        
        # Check ignores
        for glob in ignore_globs:
            # Handle directory recursion: if glob is dir (ends with / or **), check prefix
            if glob.endswith("/**") or "**" in glob:
                pattern = glob.replace("/**", "/*")  # Simplify for fnmatch
                if rel_path.startswith(glob.rstrip("/**").rstrip("/") + "/") or fnmatch.fnmatch(rel_path, pattern):
                    logging.debug(f"Ignoring path due to recursive glob '{glob}': {rel_path}")
                    return True
            elif glob.endswith("/"):
                dir_name = glob.rstrip("/")
                if rel_path.startswith(dir_name + "/") or rel_path == dir_name:
                    logging.debug(f"Ignoring directory and contents '{dir_name}': {rel_path}")
                    return True
            elif fnmatch.fnmatch(rel_path, glob):
                logging.debug(f"Ignoring path due to glob '{glob}': {rel_path}")
                return True
        
        # Always ignore .gitignore itself unless un-ignored
        if rel_path == ".gitignore":
            return True
        
        return False

    # Build file structure, excluding ignored files/dirs
    structure: List[str] = []
    files_to_write: List[Tuple[str, str, str]] = []  # rel_path, lang, content
    for path in folder.rglob("*"):
        rel_path = path.relative_to(folder).as_posix()
        if is_ignored(rel_path):
            continue
        if path.is_dir():
            structure.append(f"{rel_path}/")
        elif path.is_file():
            structure.append(rel_path)
            try:
                content = path.read_text(encoding="utf-8")
                # Escape backticks and other potential MD breakers
                content = content.replace("```", r"\`\`\`").replace(r"\```", r"\\```")  # Double-escape if needed
                ext = path.suffix.lstrip(".")
                lang = ext if ext in ("py", "js", "json", "md", "txt", "sh") else "text"
                files_to_write.append((rel_path, lang, content))
                file_list.append(rel_path)
            except UnicodeDecodeError:
                warnings.append(f"Failed to read {rel_path} (non-UTF-8 encoding)")
                logging.warning(f"Skipping non-UTF-8 file: {rel_path}")
            except Exception as e:
                warnings.append(f"Failed to read {rel_path}: {str(e)}")
                logging.warning(f"Failed to read {rel_path}: {str(e)}")

    # Generate Markdown content in reproducible format
    md_content = ["# Generated Folder Structure", "## File Structure", "```text"]
    for entry in sorted(structure):
        md_content.append(entry)
    md_content.append("```")

    for rel_path, lang, content in sorted(files_to_write):  # Sort for consistency
        md_content.extend([
            f"\n## {rel_path}",
            f"```{lang}\n{content.rstrip()}\n```"
        ])

    # Write Markdown file
    try:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text("\n".join(md_content), encoding="utf-8")
        logging.info(f"Wrote Markdown to {output_md}")
    except Exception as e:
        warnings.append(f"Failed to write {output_md}: {str(e)}")
        logging.error(f"Failed to write {output_md}: {str(e)}")

    # Compare structure if enabled
    if compare:
        code_map = {rel_path: [content] for rel_path, _, content in files_to_write}
        verify_warnings: List[str] = []
        verify_output(folder, structure, code_map, verify_warnings)
        warnings.extend(verify_warnings)

    return file_list, warnings