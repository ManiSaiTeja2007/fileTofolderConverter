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
) -> Tuple[Dict[str, List[str]], List[str], List[str], Dict[str, str]]:
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

    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        # heading handling
        if tok.type == "heading_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            heading_text_stripped = heading_text.strip().replace('\\', '/')
            if heading_text_stripped.lower() == "file structure":
                current_file = None
                current_heading = None
                skip_next_fence_for_file_structure = True
            else:
                # Try exact match first
                if heading_text_stripped in code_map:
                    current_file = heading_text_stripped
                    current_heading = heading_text
                    heading_map[current_file] = heading_text
                else:
                    # Try partial path matches (e.g., src/app/login/page.tsx)
                    candidates = [f for f in code_map.keys() if heading_text_stripped.endswith(f) or f.endswith(heading_text_stripped)]
                    if len(candidates) == 1:
                        current_file = candidates[0]
                        current_heading = heading_text
                        heading_map[current_file] = heading_text
                        warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{current_file}' via partial path")
                    else:
                        # Try basename match
                        basename = Path(heading_text_stripped).name
                        if basename in basename_lookup and len(basename_lookup[basename]) == 1:
                            current_file = basename_lookup[basename][0]
                            current_heading = heading_text
                            heading_map[current_file] = heading_text
                            warnings.append(f"ℹ️ Matched heading '{heading_text}' to file '{current_file}' via basename")
                        else:
                            current_file = None
                            current_heading = None
                            if candidates:
                                warnings.append(f"⚠️ Ambiguous heading '{heading_text}' matches multiple files: {candidates}")
                            else:
                                warnings.append(f"⚠️ Heading '{heading_text}' does not match any file in tree")
            i += 1
            continue

        # fence blocks
        if tok.type == "fence":
            fence_info = getattr(tok, "info", "") or ""
            fence_info = fence_info.strip()
            fence_content = textwrap.dedent(tok.content).rstrip()
            # Unescape backticks to restore original content
            fence_content = fence_content.replace(r"\\`\`\`", "\`\`\`")

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
                target = exact[0]
                code_map[target].append(fence_content)
                heading_map[target] = fence_info
                warnings.append(f"ℹ️ Assigned fenced block (exact info='{fence_info}') -> {target}")
                i += 1
                continue
            if len(candidates) == 1:
                target = candidates[0]
                code_map[target].append(fence_content)
                heading_map[target] = fence_info
                warnings.append(f"ℹ️ Assigned fenced block (info='{fence_info}') -> {target}")
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
                hint = hint.lstrip("./").replace('\\', '/')
                candidates2 = [f for f in code_map.keys() if f.endswith(hint) or hint in f]
                if len(candidates2) == 1:
                    target = candidates2[0]
                    if strip_hints:
                        body = "\n".join(fence_content.splitlines()[1:]).rstrip()
                    else:
                        body = fence_content
                    if body:
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
                    code_map[target].append(fence_content)
                    heading_map[target] = fence_basename
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
    return code_map, unassigned, warnings, heading_map