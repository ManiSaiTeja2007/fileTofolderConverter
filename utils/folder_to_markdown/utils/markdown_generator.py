"""Markdown content generation utilities."""
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

def generate_markdown_content(
    folder: Path,
    tree_lines: List[str],
    files_to_write: List[Tuple[str, str, str]],
    warnings: List[str]
) -> List[str]:
    """
    Generate complete Markdown content from folder structure and files.
    """
    md_content = [
        "# Generated Folder Structure",
        f"*Generated from: `{folder}`*",
        f"*Timestamp: {datetime.now().isoformat()}*",
        "",
        "## File Structure",
        "```text"
    ]
    
    full_tree_for_display = [f"{folder.name}/"] + tree_lines
    md_content.extend(full_tree_for_display)
    md_content.append("```")

    # Add file contents
    for rel_path, lang, content in sorted(files_to_write, key=lambda x: x[0].lower()):
        md_content.extend([
            f"\n## {rel_path}",
            f"```{lang}",
            content,
            "```"
        ])

    # Add summary
    md_content.extend([
        "\n## Summary",
        f"- Total files: {len(files_to_write)}",
        f"- Total directories: {len([l for l in tree_lines if l.endswith('/')])}",
        f"- Warnings: {len(warnings)}"
    ])
    
    return md_content