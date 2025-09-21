from pathlib import Path
from typing import List, Tuple
import re
import logging

from utils.verify_output.verify_output import verify_output  # For comparison

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

def folder_to_markdown(folder: Path, output_md: Path, compare: bool = True) -> Tuple[List[str], List[str]]:
    """
    Convert a folder to a Markdown file with file structure and contents, respecting .gitignore.
    The output MD is formatted to be reproducible (parsable back to folder).
    Escapes backticks in file contents to prevent parser confusion.
    Args:
        folder: Path to the input folder.
        output_md: Path to the output Markdown file.
        compare: Whether to compare generated structure against folder (default: True).
    Returns:
        Tuple of (file_list, warnings): List of files written to MD, and any warnings.
    """
    warnings: List[str] = []
    file_list: List[str] = []
    
    # Parse .gitignore if present
    ignore_patterns = []
    gitignore_path = folder / ".gitignore"
    if gitignore_path.exists():
        try:
            with gitignore_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        pattern = line.replace(".", r"\.").replace("*", ".*")
                        ignore_patterns.append(re.compile(pattern))
        except Exception as e:
            warnings.append(f"Failed to parse .gitignore: {str(e)}")

    # Build file structure, excluding ignored files
    def is_ignored(path: Path) -> bool:
        rel_path = path.relative_to(folder).as_posix()
        return any(pat.match(rel_path) for pat in ignore_patterns) or path.name == ".gitignore"

    structure: List[str] = []
    files_to_write: List[Tuple[str, str, str]] = []  # rel_path, lang, content
    for path in folder.rglob("*"):
        if is_ignored(path):
            continue
        rel_path = path.relative_to(folder).as_posix()
        if path.is_dir():
            structure.append(f"{rel_path}/")
        elif path.is_file():
            structure.append(rel_path)
            try:
                content = path.read_text(encoding="utf-8")
                # Escape backticks to prevent parser confusion
                content = content.replace("```", r"\```")
                ext = path.suffix.lstrip(".")
                lang = ext if ext in ("py", "js", "json", "md", "txt", "sh") else "text"
                files_to_write.append((rel_path, lang, content))
                file_list.append(rel_path)
            except Exception as e:
                warnings.append(f"Failed to read {rel_path}: {str(e)}")

    # Generate Markdown content in reproducible format
    md_content = ["# Generated Folder Structure", "## File Structure", "```text"]
    for entry in sorted(structure):
        md_content.append(entry)
    md_content.append("```")

    for rel_path, lang, content in files_to_write:
        md_content.extend([
            f"\n## {rel_path}",
            f"```{lang}\n{content.rstrip()}\n```"
        ])

    # Write Markdown file
    try:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text("\n".join(md_content), encoding="utf-8")
    except Exception as e:
        warnings.append(f"Failed to write {output_md}: {str(e)}")

    # Compare structure if enabled
    if compare:
        code_map = {rel_path: [content] for rel_path, _, content in files_to_write}
        verify_warnings: List[str] = []
        verify_output(folder, structure, code_map, verify_warnings)
        warnings.extend(verify_warnings)

    return file_list, warnings