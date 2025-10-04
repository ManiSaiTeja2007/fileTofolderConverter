from pathlib import Path
from typing import List, Tuple, Set, Optional
import re
import logging
import fnmatch

from utils.verify_output.verify_output import verify_output
from utils.is_probably_file.is_probably_file import is_probably_file

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
    ".git/**",
]

def pattern_to_regex(pattern: str) -> str:
    """Convert .gitignore or glob pattern to regex, handling globs and paths."""
    pattern = pattern.strip()
    if not pattern or pattern.startswith("#"):
        return ""
    # Handle directory-specific patterns (e.g., dir/)
    if pattern.endswith("/"):
        pattern = pattern[:-1]
    # Convert ** to match any path
    if "**" in pattern:
        pattern = pattern.replace("/**", "(/.*)?")
    # Escape special regex chars, convert globs
    pattern = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    # Ensure pattern matches whole path segments
    return f"^{pattern}$"

def load_gitignore_patterns(gitignore_path: Path) -> Tuple[Set[str], Set[str]]:
    """Load .gitignore patterns, separating ignores and un-ignores (!patterns)."""
    ignores = set()
    unignores = set()
    if gitignore_path.exists():
        try:
            with gitignore_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if line.startswith("!"):
                            pattern = pattern_to_regex(line[1:].rstrip("/"))
                            if pattern:
                                unignores.add(pattern)
                        else:
                            pattern = pattern_to_regex(line.rstrip("/"))
                            if pattern:
                                ignores.add(pattern)
        except Exception as e:
            logging.warning(f"⚠️ Failed to parse .gitignore at {gitignore_path}: {e}")
    return ignores, unignores

def build_ascii_tree(
    root: Path,
    ignore_patterns: Set[str],
    unignore_patterns: Set[str],
    files_always: Set[str],
    dirs_always: Set[str]
) -> List[str]:
    """Generate ASCII tree representation of directory structure, excluding ignored paths."""
    def _walk_dir(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
        lines = []
        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError as e:
            logging.warning(f"⚠️ Permission denied for {path}: {e}")
            return [f"{prefix}└── {path.name}/ # Permission denied"]
        except Exception as e:
            logging.warning(f"⚠️ Failed to read directory {path}: {e}")
            return [f"{prefix}└── {path.name}/ # Error"]

        default_ignore_regexes = {pattern_to_regex(pat) for pat in DEFAULT_IGNORE_PATTERNS}

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            name = entry.name
            rel_path = str(entry.relative_to(root)).replace("\\", "/")

            # Explicitly skip __pycache__ directory
            if name == "__pycache__":
                logging.debug(f"Ignoring __pycache__ directory: {rel_path}")
                continue

            # Check if path is un-ignored (negation takes precedence)
            if any(re.match(pat, rel_path) for pat in unignore_patterns):
                logging.debug(f"Un-ignoring path: {rel_path}")
            elif any(re.match(pat, rel_path) for pat in default_ignore_regexes | ignore_patterns):
                logging.debug(f"Ignoring path due to pattern match: {rel_path}")
                continue

            # Determine if entry is a file or directory
            is_file = is_probably_file(name, files_always, dirs_always)
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}{'/' if entry.is_dir() and not is_file else ''}")

            if entry.is_dir() and not is_file:
                new_prefix = prefix + ("    " if is_last else "│   ")
                lines.extend(_walk_dir(entry, new_prefix, depth + 1))
        
        return lines

    try:
        tree_lines = _walk_dir(root)
        if not tree_lines:
            logging.warning("⚠️ No entries found in directory tree")
            return ["# Empty directory"]
        return tree_lines
    except Exception as e:
        logging.error(f"❌ Failed to build ASCII tree for {root}: {e}")
        return ["# Error building directory tree"]

def folder_to_markdown(
    folder: Path,
    output_md: Path,
    compare: bool = True,
    user_ignore: Optional[List[str]] = None,
    files_always: Optional[Set[str]] = None,
    dirs_always: Optional[Set[str]] = None
) -> Tuple[List[str], List[str]]:
    """
    Convert a folder to a Markdown file with ASCII tree structure and file contents.
    Respects .gitignore, user-provided ignores, and default ignore patterns.
    Escapes backticks in file contents to prevent Markdown parser issues.
    Args:
        folder: Path to the input folder.
        output_md: Path to the output Markdown file.
        compare: Whether to compare generated structure against folder (default: True).
        user_ignore: List of user-provided ignore patterns from --ignore flag.
        files_always: Set of names to treat as files (e.g., 'Dockerfile').
        dirs_always: Set of names to treat as directories.
    Returns:
        Tuple of (file_list, warnings): List of files written to MD, and any warnings.
    """
    warnings: List[str] = []
    file_list: List[str] = []
    files_always = files_always or {"dockerfile", "makefile", "readme", "readme.md", "license", ".gitignore", ".eslintrc", ".editorconfig"}
    dirs_always = dirs_always or set()

    if not folder.is_dir():
        warnings.append(f"❌ Input {folder} is not a directory")
        logging.error(f"❌ Input {folder} is not a directory")
        return [], warnings

    # Combine ignore patterns
    ignore_globs = DEFAULT_IGNORE_PATTERNS[:]
    if user_ignore:
        ignore_globs.extend(user_ignore)
    
    # Load .gitignore patterns
    gitignore_path = folder / ".gitignore"
    gitignore_ignores, gitignore_unignores = load_gitignore_patterns(gitignore_path)

    # Build ASCII tree
    tree_lines = build_ascii_tree(folder, gitignore_ignores, gitignore_unignores, files_always, dirs_always)

    # Collect files to write
    files_to_write: List[Tuple[str, str, str]] = []  # rel_path, lang, content
    default_ignore_regexes = {pattern_to_regex(pat) for pat in ignore_globs}
    for path in folder.rglob("*"):
        rel_path = path.relative_to(folder).as_posix()
        # Check if path is un-ignored
        if any(re.match(pat, rel_path) for pat in gitignore_unignores):
            logging.debug(f"Un-ignoring path: {rel_path}")
        elif any(re.match(pat, rel_path) for pat in default_ignore_regexes | gitignore_ignores):
            continue

        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="replace").rstrip()
                # Escape backticks to prevent Markdown parser issues
                content = content.replace("```", r"\`\`\`").replace(r"\```", r"\\```")
                ext = path.suffix.lstrip(".").lower()
                lang = {
                    "py": "python",
                    "js": "javascript",
                    "ts": "typescript",
                    "tsx": "tsx",
                    "jsx": "jsx",
                    "json": "json",
                    "md": "markdown",
                    "yml": "yaml",
                    "yaml": "yaml",
                    "sh": "bash",
                    "css": "css",
                    "html": "html",
                    "txt": "text"
                }.get(ext, "text")
                files_to_write.append((rel_path, lang, content))
                file_list.append(rel_path)
            except UnicodeDecodeError:
                warnings.append(f"⚠️ Skipped {rel_path}: Binary or non-text file")
                logging.warning(f"⚠️ Skipped {rel_path}: Binary or non-text file")
            except Exception as e:
                warnings.append(f"⚠️ Failed to read {rel_path}: {str(e)}")
                logging.warning(f"⚠️ Failed to read {rel_path}: {str(e)}")

    # Generate Markdown content
    md_content = ["# Generated Folder Structure", "", "## File Structure", "```text"]
    full_tree_for_display = [f"{folder.name}/"] + tree_lines
    md_content.extend(full_tree_for_display)
    md_content.append("```")

    for rel_path, lang, content in sorted(files_to_write, key=lambda x: x[0].lower()):
        md_content.extend([
            f"\n## {rel_path}",
            f"```{lang}",
            content,
            "```"
        ])

    # Write Markdown file
    try:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text("\n".join(md_content), encoding="utf-8")
        logging.info(f"✅ Wrote Markdown to {output_md}")
    except Exception as e:
        warnings.append(f"❌ Failed to write {output_md}: {str(e)}")
        logging.error(f"❌ Failed to write {output_md}: {str(e)}")
        return file_list, warnings

    # Compare structure if enabled
    if compare:
        try:
            from utils.load_markdown.load_markdown import load_markdown
            from utils.extract_file_structure_block.extract_file_structure_block import extract_file_structure_block
            from utils.parse_ascii_tree_block.parse_ascii_tree_block import parse_ascii_tree_block
            md_text, tokens = load_markdown(output_md)
            fs_block = extract_file_structure_block(md_text, tokens)
            if fs_block:
                parsed_files = parse_ascii_tree_block(fs_block, files_always, dirs_always)
                parsed_set = set(f for f in parsed_files if is_probably_file(Path(f).name, files_always, dirs_always))
                print(f"Parsed files: {parsed_set}")
                generated_set = set(file_list)
                print(f"Generated files: {generated_set}")
                if parsed_set != generated_set:
                    warnings.append("⚠️ Generated file structure does not match parsed structure")
            else:
                warnings.append("⚠️ No file structure block found in generated Markdown")
            # Verify output structure
            code_map = {rel_path: [content] for rel_path, _, content in files_to_write}
            verify_warnings: List[str] = []
            verify_output(folder, [f for f in tree_lines if not f.startswith("#") and is_probably_file(Path(f.strip("├──└── │")).name, files_always, dirs_always)], code_map, verify_warnings)
            warnings.extend(verify_warnings)
        except Exception as e:
            warnings.append(f"⚠️ Failed to verify generated Markdown: {str(e)}")
            logging.warning(f"⚠️ Failed to verify generated Markdown: {str(e)}")

    return file_list, warnings