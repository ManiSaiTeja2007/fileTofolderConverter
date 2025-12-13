"""Structure comparison utilities."""
from pathlib import Path
from typing import List, Tuple, Set, Dict
import logging

# Import from project utils
from utils.is_probably_file.is_probably_file import is_probably_file
from utils.verify_output.verify_output import verify_output

def compare_structure(
    folder: Path,
    files_to_write: List[Tuple[str, str, str]],
    tree_lines: List[str],
    files_always: Set[str],
    dirs_always: Set[str],
    warnings: List[str],
    output_md: Path,
    file_list: List[str]
) -> None:
    """Compare generated structure against actual folder structure."""
    from utils.load_markdown.load_markdown import load_markdown
    from utils.extract_file_structure_block.extract_file_structure_block import extract_file_structure_block
    from utils.parse_ascii_tree_block.parse_ascii_tree_block import parse_ascii_tree_block
    
    md_text, tokens = load_markdown(output_md)
    fs_block = extract_file_structure_block(md_text, tokens)
    
    if fs_block:
        parsed_files = parse_ascii_tree_block(fs_block, files_always, dirs_always)
        compare_file_sets(folder, parsed_files, file_list, files_always, dirs_always, warnings)
    
    # Verify output structure
    verify_output_structure(folder, files_to_write, tree_lines, files_always, dirs_always, warnings)

def compare_file_sets(
    folder: Path,
    parsed_files: List[str],
    file_list: List[str],
    files_always: Set[str],
    dirs_always: Set[str],
    warnings: List[str]
) -> None:
    """Compare parsed files from markdown with generated file list."""
    folder_name = folder.name
    parsed_set = set()
    for file_path in parsed_files:
        if is_probably_file(Path(file_path).name, files_always, dirs_always):
            # Remove folder name prefix if present
            if file_path.startswith(folder_name + '/'):
                parsed_set.add(file_path[len(folder_name) + 1:])
            else:
                parsed_set.add(file_path)

    generated_set = set(file_list)
    if parsed_set != generated_set:
        missing = generated_set - parsed_set
        extra = parsed_set - generated_set
        if missing:
            warnings.append(f"⚠️ Files in folder but not in markdown: {missing}")
        if extra:
            warnings.append(f"⚠️ Files in markdown but not in folder: {extra}")

def verify_output_structure(
    folder: Path,
    files_to_write: List[Tuple[str, str, str]],
    tree_lines: List[str],
    files_always: Set[str],
    dirs_always: Set[str],
    warnings: List[str]
) -> None:
    """Verify output structure using external verification."""
    code_map = {rel_path: [content] for rel_path, _, content in files_to_write}
    verify_warnings: List[str] = []
    
    file_tree_lines = [
        f for f in tree_lines 
        if not f.startswith("#") and is_probably_file(
            Path(f.strip("├──└── │")).name, files_always, dirs_always
        )
    ]
    
    verify_output(folder, file_tree_lines, code_map, verify_warnings)
    warnings.extend(verify_warnings)