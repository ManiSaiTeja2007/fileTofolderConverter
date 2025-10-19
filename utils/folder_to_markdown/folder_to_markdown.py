from pathlib import Path
from typing import List, Tuple, Set, Optional
import logging

from ..constants import DEFAULT_IGNORE_PATTERNS
from .utils.pattern_matcher import load_gitignore_patterns
from .utils.tree_builder import build_ascii_tree
from .utils.file_processor import collect_files
from .utils.markdown_generator import generate_markdown_content
from .utils.structure_comparator import compare_structure

def folder_to_markdown(
    folder: Path,
    output_md: Path,
    compare: bool = True,
    user_ignore: Optional[List[str]] = None,
    files_always: Optional[Set[str]] = None,
    dirs_always: Optional[Set[str]] = None,
    max_depth: int = 20,
    max_file_size: int = 1024 * 1024
) -> Tuple[List[str], List[str]]:
    """
    Convert a folder to a Markdown file with ASCII tree structure and file contents.
    """
    warnings: List[str] = []
    file_list: List[str] = []
    
    # Default configurations
    files_always = files_always or {
        "dockerfile", "makefile", "readme", "readme.md", "license", 
        ".gitignore", ".eslintrc", ".editorconfig", ".prettierrc"
    }
    dirs_always = dirs_always or set()

    # Validation
    if not folder.is_dir():
        error_msg = f"❌ Input {folder} is not a directory"
        warnings.append(error_msg)
        logging.error(error_msg)
        return [], warnings

    # Combine ignore patterns
    ignore_globs = DEFAULT_IGNORE_PATTERNS[:]
    if user_ignore:
        ignore_globs.extend(user_ignore)
    
    # Load .gitignore patterns
    gitignore_path = folder / ".gitignore"
    gitignore_ignores, gitignore_unignores = load_gitignore_patterns(gitignore_path)

    # Build ASCII tree
    tree_lines = build_ascii_tree(
        folder, gitignore_ignores, gitignore_unignores, 
        files_always, dirs_always, max_depth
    )

    # Collect files
    files_to_write, collect_warnings = collect_files(
        folder, gitignore_ignores, gitignore_unignores,
        files_always, dirs_always, max_file_size
    )
    warnings.extend(collect_warnings)
    
    file_list = [rel_path for rel_path, _, _ in files_to_write]

    # Generate and write Markdown content
    md_content = generate_markdown_content(folder, tree_lines, files_to_write, warnings)
    
    try:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text("\n".join(md_content), encoding="utf-8")
        logging.info(f"✅ Wrote Markdown to {output_md} ({len(files_to_write)} files)")
    except Exception as e:
        error_msg = f"❌ Failed to write {output_md}: {str(e)}"
        warnings.append(error_msg)
        logging.error(error_msg)
        return file_list, warnings

    # Compare structure if enabled
    if compare:
        try:
            compare_structure(folder, files_to_write, tree_lines, files_always, dirs_always, warnings, output_md, file_list)
        except Exception as e:
            warning_msg = f"⚠️ Failed to verify generated Markdown: {str(e)}"
            warnings.append(warning_msg)
            logging.warning(warning_msg)

    return file_list, warnings

def quick_export(
    source_folder: str,
    output_file: str = "structure.md",
    ignore_patterns: Optional[List[str]] = None
) -> None:
    """
    Quick export function for common use cases.
    """
    folder = Path(source_folder)
    output = Path(output_file)
    
    if not folder.exists():
        print(f"Error: Folder {source_folder} does not exist")
        return
        
    files, warnings = folder_to_markdown(
        folder=folder,
        output_md=output,
        user_ignore=ignore_patterns
    )
    
    print(f"Exported {len(files)} files to {output_file}")
    for warning in warnings:
        print(f"Warning: {warning}")