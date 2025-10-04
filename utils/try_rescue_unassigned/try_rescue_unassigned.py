from typing import List, Tuple, Dict
import re
import difflib
from pathlib import Path
import logging

def try_rescue_unassigned(
    unassigned: List[str],
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    heading_map: Dict[str, str],
    strip_hints: bool,
    interactive: bool,
    fallback_level: str = "high",
) -> Tuple[List[str], List[str]]:
    """
    Attempt to rescue unassigned code blocks by matching hints or headings.
    Args:
        unassigned: List of unassigned code blocks.
        tree_entries: List of file paths from the ASCII tree.
        code_map: Dict mapping file paths to lists of code block contents.
        heading_map: Dict mapping file paths to their corresponding headings.
        strip_hints: Whether to strip first-line hint comments.
        interactive: Whether to prompt for conflict resolution (not implemented here).
        fallback_level: Rescue strictness ('low': exact matches, 'medium': fuzzy matches, 'high': auto-assign).
    Returns:
        Tuple of (still_unassigned, rescued_warnings): Unassigned blocks and warnings.
    """
    rescued_warnings: List[str] = []
    still_unassigned: List[str] = []

    def get_path_specificity(path: str) -> int:
        """Count path segments for specificity (e.g., 'utils/file.py' -> 2)."""
        return len(Path(path).parts)

    def are_hints_similar(hint1: str, hint2: str, threshold: float = 0.8) -> bool:
        """Check if two hints are similar using difflib (returns True if similarity >= threshold)."""
        return difflib.SequenceMatcher(None, hint1.lower(), hint2.lower()).ratio() >= threshold

    for code in unassigned:
        if not code.strip():
            rescued_warnings.append("⚠️ Skipped empty code block")
            continue

        lines = code.splitlines()
        hint = None
        hint_line_num = -1

        # Check for comment-based hint in first two lines
        try:
            for l in range(min(2, len(lines))):
                line = lines[l]
                m = re.match(r"^(\s*//\s*|\s*#\s*)(.*)$", line)
                if m:
                    hint = m.group(2).strip().lstrip("./").replace('\\', '/')
                    hint_line_num = l
                    break
        except Exception as e:
            rescued_warnings.append(f"⚠️ Failed to parse hint in code block: {e}")
            still_unassigned.append(code)
            continue

        # Try to match hint
        if hint:
            candidates = []
            for f in code_map.keys():
                if f == hint:
                    candidates = [f]
                    break
                if f.endswith(hint):
                    candidates.append(f)
            if not candidates and fallback_level in ("medium", "high"):
                candidates = [f for f in code_map.keys() if hint in f]
            if not candidates and fallback_level in ("medium", "high"):
                candidates = difflib.get_close_matches(hint, code_map.keys(), n=1, cutoff=0.8)

            if len(candidates) == 1:
                target = candidates[0]
                existing_hint = hint if hint_line_num >= 0 else ""
                body = code
                if existing_hint and are_hints_similar(existing_hint, target):
                    if get_path_specificity(existing_hint) >= get_path_specificity(target):
                        body = "\n".join(lines).rstrip()
                    else:
                        body = "\n".join(lines[:hint_line_num] + lines[hint_line_num + 1:]).rstrip() if strip_hints else f"# {target}\n{code.lstrip()}"
                        rescued_warnings.append(f"ℹ️ Replaced hint '{existing_hint}' with '{target}' (more specific)")
                elif strip_hints and hint_line_num >= 0:
                    body = "\n".join(lines[:hint_line_num] + lines[hint_line_num + 1:]).rstrip()
                if body:
                    if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                        rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                    code_map[target].append(body)
                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from hint '{hint}')")
                continue
            elif len(candidates) > 1:
                if interactive:
                    # Placeholder for interactive resolution (not implemented)
                    rescued_warnings.append(f"⚠️ Ambiguous hint '{hint}' matches {candidates}; kept unassigned (interactive not implemented)")
                else:
                    rescued_warnings.append(f"⚠️ Ambiguous hint '{hint}' matches {candidates}; kept unassigned")
                still_unassigned.append(code)
                continue
            else:
                rescued_warnings.append(f"⚠️ Hint '{hint}' did not match any file")
                if fallback_level == "high":
                    # Auto-assign to closest basename match
                    basename = Path(hint).name
                    basename_matches = [f for f in code_map.keys() if Path(f).name == basename]
                    if len(basename_matches) == 1:
                        target = basename_matches[0]
                        body = "\n".join(lines[:hint_line_num] + lines[hint_line_num + 1:]).rstrip() if strip_hints and hint_line_num >= 0 else code
                        if body:
                            if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                                rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                            code_map[target].append(body)
                        rescued_warnings.append(f"ℹ️ Auto-assigned block to {target} (basename match for hint '{hint}')")
                        continue
                still_unassigned.append(code)
                continue

        # No hint in comments, try first line as assumed heading
        if lines and fallback_level in ("medium", "high"):
            hint = lines[0].strip().lstrip("./").replace('\\', '/')
            candidates = []
            for f in code_map.keys():
                if f == hint:
                    candidates = [f]
                    break
                if f.endswith(hint):
                    candidates.append(f)
            if not candidates:
                candidates = [f for f in code_map.keys() if hint in f]
            if not candidates:
                candidates = difflib.get_close_matches(hint, code_map.keys(), n=1, cutoff=0.8)

            if len(candidates) == 1:
                target = candidates[0]
                body = "\n".join(lines[1:]).rstrip() if strip_hints else code
                if body:
                    if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                        rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                    code_map[target].append(body)
                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from assumed heading '{hint}')")
                continue
            elif len(candidates) > 1:
                if interactive:
                    rescued_warnings.append(f"⚠️ Ambiguous assumed heading '{hint}' matches {candidates}; kept unassigned (interactive not implemented)")
                else:
                    rescued_warnings.append(f"⚠️ Ambiguous assumed heading '{hint}' matches {candidates}; kept unassigned")
                still_unassigned.append(code)
                continue

        # Try to match with heading_map entries
        if fallback_level in ("medium", "high"):
            for target, heading in heading_map.items():
                heading_clean = heading.strip().lstrip("./").replace('\\', '/')
                if heading_clean in code_map and code.startswith(heading):
                    body = "\n".join(lines[1:]).rstrip() if strip_hints else code
                    if body:
                        if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                            rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                        code_map[target].append(body)
                    rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from heading '{heading}')")
                    break
            else:
                if fallback_level == "high":
                    # Auto-assign to closest file by content similarity
                    candidates = difflib.get_close_matches(code[:100], [c for f in code_map for c in code_map[f]], n=1, cutoff=0.6)
                    if candidates:
                        for target, contents in code_map.items():
                            if candidates[0] in contents:
                                body = code
                                if code_map[target] and are_hints_similar(code_map[target][-1].splitlines()[0], target):
                                    rescued_warnings.append(f"⚠️ File {target} had multiple code blocks merged")
                                code_map[target].append(body)
                                rescued_warnings.append(f"ℹ️ Auto-assigned block to {target} (content similarity)")
                                break
                        else:
                            still_unassigned.append(code)
                    else:
                        still_unassigned.append(code)
                else:
                    still_unassigned.append(code)
        else:
            still_unassigned.append(code)

    return still_unassigned, rescued_warnings