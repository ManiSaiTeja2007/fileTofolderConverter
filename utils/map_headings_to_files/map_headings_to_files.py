from typing import Dict, List, Tuple, Optional
from pathlib import Path
from markdown_it.token import Token
import textwrap
import re
import difflib

from utils.infer_targets_from_fence_info.infer_targets_from_fence_info import infer_targets_from_fence_info
from utils.is_probably_file.is_probably_file import is_probably_file

def map_headings_to_files(
    tokens: List[Token],
    tree_files: List[str],
    files_always: set,
    dirs_always: set,
    strip_hints: bool,
    interactive: bool
) -> Tuple[Dict[str, List[str]], List[str], List[str], Dict[str, str]]:
    """
    Map Markdown headings and code blocks to files in the tree, handling hints and fuzzy matching.
    Args:
        tokens: List of Markdown tokens.
        tree_files: List of file paths from the ASCII tree.
        files_always: Set of names to treat as files.
        dirs_always: Set of names to treat as directories.
        strip_hints: Whether to strip first-line hint comments.
        interactive: Whether to prompt for conflict resolution (not implemented here).
    Returns:
        Tuple of (code_map, unassigned, warnings, heading_map):
            - code_map: Dict mapping file paths to lists of code block contents.
            - unassigned: List of unassigned code blocks.
            - warnings: List of warnings for ambiguous matches or hint handling.
            - heading_map: Dict mapping file paths to their corresponding headings.
    """
    code_map: Dict[str, List[str]] = {
        f: [] for f in tree_files if is_probably_file(Path(f).name, files_always, dirs_always)
    }
    heading_map: Dict[str, str] = {}
    unassigned: List[str] = []
    warnings: List[str] = []

    basename_lookup: Dict[str, List[str]] = {}
    for f in code_map.keys():
        basename_lookup.setdefault(Path(f).name, []).append(f)

    current_file: Optional[str] = None
    current_heading: Optional[str] = None
    skip_next_fence_for_file_structure = False

    def get_path_specificity(path: str) -> int:
        """Count path segments for specificity (e.g., 'utils/file.py' -> 2)."""
        return len(Path(path).parts)

    def are_hints_similar(hint1: str, hint2: str, threshold: float = 0.8) -> bool:
        """Check if two hints are similar using difflib (returns True if similarity >= threshold)."""
        return difflib.SequenceMatcher(None, hint1.lower(), hint2.lower()).ratio() >= threshold

    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        # Heading handling
        if tok.type == "heading_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            heading_text_stripped = heading_text.strip().replace('\\', '/').lstrip("./")
            if heading_text_stripped.lower() == "file structure":
                current_file = None
                current_heading = None
                skip_next_fence_for_file_structure = True
            else:
                # Try exact match
                if heading_text_stripped in code_map:
                    current_file = heading_text_stripped
                    current_heading = heading_text
                    heading_map[current_file] = heading_text
                else:
                    # Try partial path matches
                    candidates = [f for f in code_map.keys() if heading_text_stripped.endswith(f) or f.endswith(heading_text_stripped)]
                    if len(candidates) == 1:
                        current_file = candidates[0]
                        current_heading = heading_text
                        heading_map[current_file] = heading_text
                        warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{current_file}' via partial path")
                    elif len(candidates) > 1:
                        warnings.append(f"⚠️ Ambiguous heading '{heading_text}' matches multiple files: {candidates}")
                        current_file = None
                        current_heading = None
                    else:
                        # Try basename match
                        basename = Path(heading_text_stripped).name
                        if basename in basename_lookup and len(basename_lookup[basename]) == 1:
                            current_file = basename_lookup[basename][0]
                            current_heading = heading_text
                            heading_map[current_file] = heading_text
                            warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{current_file}' via basename")
                        else:
                            # Fuzzy matching fallback
                            fuzzy_matches = difflib.get_close_matches(heading_text_stripped, code_map.keys(), n=1, cutoff=0.8)
                            if fuzzy_matches:
                                current_file = fuzzy_matches[0]
                                current_heading = heading_text
                                heading_map[current_file] = heading_text
                                warnings.append(f"ℹ️ Fuzzy matched heading '{heading_text}' to file '{current_file}'")
                            else:
                                warnings.append(f"⚠️ Heading '{heading_text}' does not match any file in tree")
                                current_file = None
                                current_heading = None
            i += 1
            continue

        # Fence blocks
        if tok.type == "fence":
            fence_info = getattr(tok, "info", "") or ""
            fence_info = fence_info.strip()
            fence_content = textwrap.dedent(tok.content).rstrip()
            # Unescape backticks to restore original content
            fence_content = fence_content.replace(r"\\```", r"```")

            if skip_next_fence_for_file_structure:
                skip_next_fence_for_file_structure = False
                i += 1
                continue

            if current_file and current_file in code_map:
                # Check for existing hint in fence_content
                first_line = fence_content.splitlines()[0] if fence_content else ""
                existing_hint = ""
                body = fence_content
                if first_line.strip().startswith(("#", "//")):
                    existing_hint = re.sub(r"^(\s*//\s*|\s*#\s*)", "", first_line).strip().lstrip("./").replace('\\', '/')
                    if are_hints_similar(existing_hint, current_file):
                        if get_path_specificity(existing_hint) >= get_path_specificity(current_file):
                            # Existing hint is as or more specific; keep original content
                            body = fence_content
                        else:
                            # New hint is more specific; replace with current_file
                            body = "\n".join(fence_content.splitlines()[1:]).rstrip() if strip_hints else f"# {current_file}\n{fence_content.lstrip()}"
                            warnings.append(f"ℹ️ Replaced hint '{existing_hint}' with '{current_file}' (more specific)")
                    elif strip_hints:
                        body = "\n".join(fence_content.splitlines()[1:]).rstrip()
                if body:
                    if code_map[current_file] and are_hints_similar(code_map[current_file][-1].splitlines()[0], current_file):
                        warnings.append(f"⚠️ File {current_file} had multiple code blocks merged")
                    code_map[current_file].append(body)
                i += 1
                continue

            # Infer via fence info
            try:
                candidates = infer_targets_from_fence_info(fence_info, list(code_map.keys()))
                # Prioritize exact basename matches
                exact = [c for c in candidates if Path(c).name.lower() == fence_info.lower()]
                if len(exact) == 1:
                    target = exact[0]
                    first_line = fence_content.splitlines()[0] if fence_content else ""
                    existing_hint = ""
                    body = fence_content
                    if first_line.strip().startswith(("#", "//")):
                        existing_hint = re.sub(r"^(\s*//\s*|\s*#\s*)", "", first_line).strip().lstrip("./").replace('\\', '/')
                        if are_hints_similar(existing_hint, target):
                            if get_path_specificity(existing_hint) >= get_path_specificity(target):
                                body = fence_content
                            else:
                                body = "\n".join(fence_content.splitlines()[1:]).rstrip() if strip_hints else f"# {target}\n{fence_content.lstrip()}"
                                warnings.append(f"ℹ️ Replaced hint '{existing_hint}' with '{target}' (more specific)")
                        elif strip_hints:
                            body = "\n".join(fence_content.splitlines()[1:]).rstrip()
                    if body:
                        if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                            warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                        code_map[target].append(body)
                    heading_map[target] = fence_info
                    warnings.append(f"ℹ️ Assigned fenced block (exact info='{fence_info}') -> {target}")
                    i += 1
                    continue
                if len(candidates) == 1:
                    target = candidates[0]
                    first_line = fence_content.splitlines()[0] if fence_content else ""
                    existing_hint = ""
                    body = fence_content
                    if first_line.strip().startswith(("#", "//")):
                        existing_hint = re.sub(r"^(\s*//\s*|\s*#\s*)", "", first_line).strip().lstrip("./").replace('\\', '/')
                        if are_hints_similar(existing_hint, target):
                            if get_path_specificity(existing_hint) >= get_path_specificity(target):
                                body = fence_content
                            else:
                                body = "\n".join(fence_content.splitlines()[1:]).rstrip() if strip_hints else f"# {target}\n{fence_content.lstrip()}"
                                warnings.append(f"ℹ️ Replaced hint '{existing_hint}' with '{target}' (more specific)")
                        elif strip_hints:
                            body = "\n".join(fence_content.splitlines()[1:]).rstrip()
                    if body:
                        if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                            warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                        code_map[target].append(body)
                    heading_map[target] = fence_info
                    warnings.append(f"ℹ️ Assigned fenced block (info='{fence_info}') -> {target}")
                    i += 1
                    continue
                if len(candidates) > 1:
                    warnings.append(f"⚠️ Ambiguous fence info '{fence_info}' matches {candidates}; kept unassigned")
                    unassigned.append(fence_content)
                    i += 1
                    continue
            except Exception as e:
                warnings.append(f"⚠️ Failed to infer targets from fence info '{fence_info}': {e}")
                unassigned.append(fence_content)
                i += 1
                continue

            # Check for hint in first line
            first_line = fence_content.splitlines()[0] if fence_content else ""
            if first_line.strip().startswith(("#", "//")):
                hint = re.sub(r"^(\s*//\s*|\s*#\s*)", "", first_line).strip().lstrip("./").replace('\\', '/')
                candidates2 = [f for f in code_map.keys() if f.endswith(hint) or hint in f]
                if len(candidates2) == 1:
                    target = candidates2[0]
                    if are_hints_similar(hint, target):
                        if get_path_specificity(hint) >= get_path_specificity(target):
                            body = fence_content
                        else:
                            body = "\n".join(fence_content.splitlines()[1:]).rstrip() if strip_hints else f"# {target}\n{fence_content.lstrip()}"
                            warnings.append(f"ℹ️ Replaced hint '{hint}' with '{target}' (more specific)")
                    elif strip_hints:
                        body = "\n".join(fence_content.splitlines()[1:]).rstrip()
                    else:
                        body = fence_content
                    if body:
                        if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                            warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                        code_map[target].append(body)
                    heading_map[target] = hint
                    warnings.append(f"ℹ️ Rescued fenced block with hint -> {target} (from hint '{hint}')")
                    i += 1
                    continue
                elif len(candidates2) > 1:
                    warnings.append(f"⚠️ Ambiguous hint '{hint}' matches {candidates2}; kept unassigned")
                    unassigned.append(fence_content)
                    i += 1
                    continue
            if fence_info:
                fence_basename = Path(fence_info).name
                if fence_basename in basename_lookup and len(basename_lookup[fence_basename]) == 1:
                    target = basename_lookup[fence_basename][0]
                    first_line = fence_content.splitlines()[0] if fence_content else ""
                    existing_hint = ""
                    body = fence_content
                    if first_line.strip().startswith(("#", "//")):
                        existing_hint = re.sub(r"^(\s*//\s*|\s*#\s*)", "", first_line).strip().lstrip("./").replace('\\', '/')
                        if are_hints_similar(existing_hint, target):
                            if get_path_specificity(existing_hint) >= get_path_specificity(target):
                                body = fence_content
                            else:
                                body = "\n".join(fence_content.splitlines()[1:]).rstrip() if strip_hints else f"# {target}\n{fence_content.lstrip()}"
                                warnings.append(f"ℹ️ Replaced hint '{existing_hint}' with '{target}' (more specific)")
                        elif strip_hints:
                            body = "\n".join(fence_content.splitlines()[1:]).rstrip()
                    if body:
                        if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                            warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                        code_map[target].append(body)
                    heading_map[target] = fence_basename
                    warnings.append(
                        f"ℹ️ Assigned fenced block (basename '{fence_basename}') -> {basename_lookup[fence_basename][0]}"
                    )
                    i += 1
                    continue
            unassigned.append(fence_content)
            i += 1
            continue

        # Handle paragraphs under headings as potential content
        if tok.type == "paragraph_open" and current_file:
            inline = tokens[i + 1] if (i + 1) < n else None
            para_text = inline.content.strip() if inline and inline.type == "inline" else ""
            if para_text:
                if code_map[current_file] and are_hints_similar(code_map[current_file][-1].splitlines()[0], current_file):
                    warnings.append(f"⚠️ File {current_file} had multiple code blocks merged")
                code_map[current_file].append(para_text)
            j = i + 1
            while j < n and tokens[j].type != "paragraph_close":
                j += 1
            i = j + 1
            continue
        i += 1
    return code_map, unassigned, warnings, heading_map