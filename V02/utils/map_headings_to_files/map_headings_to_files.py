from typing import Dict, List, Tuple, Optional
from pathlib import Path
from markdown_it.token import Token
import textwrap
import re

from utils.infer_targets_from_fence_info.infer_targets_from_fence_info import infer_targets_from_fence_info
from utils.is_probably_file.is_probably_file import is_probably_file

def map_headings_to_files(
    tokens: List[Token],
    tree_files: List[str],
    files_always: set,
    dirs_always: set,
    strip_hints: bool,
) -> Tuple[Dict[str, List[str]], List[str], List[str]]:
    code_map: Dict[str, List[str]] = {
        f: [] for f in tree_files if is_probably_file(Path(f).name, files_always, dirs_always)
    }
    unassigned: List[str] = []
    warnings: List[str] = []

    basename_lookup: Dict[str, List[str]] = {}
    for f in code_map.keys():
        basename_lookup.setdefault(Path(f).name, []).append(f)

    current_file: Optional[str] = None
    skip_next_fence_for_file_structure = False

    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        # heading handling
        if tok.type == "heading_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            heading_text_stripped = heading_text.strip()
            if heading_text_stripped.lower() == "file structure":
                current_file = None
                skip_next_fence_for_file_structure = True
            else:
                if heading_text_stripped in code_map:
                    current_file = heading_text_stripped
                else:
                    basename = Path(heading_text_stripped).name
                    if basename in basename_lookup and len(basename_lookup[basename]) == 1:
                        current_file = basename_lookup[basename][0]
                    else:
                        current_file = None
            i += 1
            continue

        # fence blocks
        if tok.type == "fence":
            fence_info = getattr(tok, "info", "") or ""
            fence_info = fence_info.strip()
            fence_content = textwrap.dedent(tok.content).rstrip()

            if skip_next_fence_for_file_structure:
                skip_next_fence_for_file_structure = False
                i += 1
                continue

            if current_file and current_file in code_map:
                code_map[current_file].append(fence_content)
                i += 1
                continue

            # infer via fence info
            candidates = infer_targets_from_fence_info(fence_info, list(code_map.keys()))
            # prioritize exact basename matches
            exact = [c for c in candidates if Path(c).name.lower() == fence_info.lower()]
            if len(exact) == 1:
                code_map[exact[0]].append(fence_content)
                warnings.append(f"ℹ️ Assigned fenced block (exact info='{fence_info}') -> {exact[0]}")
                i += 1
                continue
            if len(candidates) == 1:
                code_map[candidates[0]].append(fence_content)
                warnings.append(f"ℹ️ Assigned fenced block (info='{fence_info}') -> {candidates[0]}")
                i += 1
                continue
            if len(candidates) > 1:
                warnings.append(f"⚠️ Ambiguous fence info '{fence_info}' matches {candidates}; kept unassigned")
                unassigned.append(fence_content)
                i += 1
                continue

            # Check for hint in first line
            first_line = fence_content.splitlines()[0] if fence_content else ""
            if first_line.strip().startswith("//") or first_line.strip().startswith("#"):
                hint = re.sub(r"^(\s*//\s*|\s*#\s*)", "", first_line).strip()
                hint = hint.lstrip("./")
                candidates2 = [f for f in code_map.keys() if f.endswith(hint) or hint in f]
                if len(candidates2) == 1:
                    target = candidates2[0]
                    if strip_hints:
                        body = "\n".join(fence_content.splitlines()[1:]).rstrip()
                    else:
                        body = fence_content
                    if body:
                        code_map[target].append(body)
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
                    code_map[basename_lookup[fence_basename][0]].append(fence_content)
                    warnings.append(
                        f"ℹ️ Assigned fenced block (basename '{fence_basename}') -> {basename_lookup[fence_basename][0]}"
                    )
                    i += 1
                    continue
            unassigned.append(fence_content)
            i += 1
            continue

        # Handle paragraphs under headings as potential content (but skip if no current_file)
        if tok.type == "paragraph_open" and current_file:
            inline = tokens[i + 1] if (i + 1) < n else None
            para_text = inline.content.strip() if inline and inline.type == "inline" else ""
            if para_text:
                code_map[current_file].append(para_text)
            j = i + 1
            while j < n and tokens[j].type != "paragraph_close":
                j += 1
            i = j + 1
            continue
        i += 1
    return code_map, unassigned, warnings