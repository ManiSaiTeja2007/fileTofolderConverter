from typing import List, Tuple, Dict
import re

def try_rescue_unassigned(
    unassigned: List[str],
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    heading_map: Dict[str, str],
    strip_hints: bool,
) -> Tuple[List[str], List[str]]:
    rescued_warnings: List[str] = []
    still_unassigned: List[str] = []

    for code in unassigned:
        lines = code.splitlines()
        hint = None
        hint_line_num = -1
        for l in range(min(2, len(lines))):
            line = lines[l]
            m = re.match(r"^(\s*//\s*|\s*#\s*)(.*)$", line)
            if m:
                hint = m.group(2).strip().lstrip("./").replace('\\', '/')
                hint_line_num = l
                break

        if hint:
            candidates = []
            for f in code_map.keys():
                if f == hint:
                    candidates = [f]
                    break
                if f.endswith(hint):
                    candidates.append(f)
            if not candidates:
                candidates = [f for f in code_map.keys() if hint in f]
            if len(candidates) == 1:
                target = candidates[0]
                if strip_hints:
                    body = "\n".join(lines[:hint_line_num] + lines[hint_line_num + 1:]).rstrip()
                else:
                    body = "\n".join(lines).rstrip()
                if body:
                    code_map[target].append(body)
                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from hint {hint})")
                continue
            elif len(candidates) > 1:
                rescued_warnings.append(f"⚠️ Ambiguous hint {hint} → matches {candidates}, kept unassigned")
                still_unassigned.append(code)
                continue
            else:
                rescued_warnings.append(f"⚠️ Hint {hint} did not match any file, kept unassigned")
                still_unassigned.append(code)
                continue

        # No hint in comments, try first line as assumed prepended heading
        if lines:
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
            if len(candidates) == 1:
                target = candidates[0]
                if strip_hints:
                    body = "\n".join(lines[1:]).rstrip()
                else:
                    body = "\n".join(lines).rstrip()
                if body:
                    code_map[target].append(body)
                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from assumed heading '{hint}')")
                continue

        # Try to match with heading_map entries
        for target, heading in heading_map.items():
            heading_clean = heading.strip().lstrip("./").replace('\\', '/')
            if heading_clean in code_map and code.startswith(heading):
                if strip_hints:
                    body = "\n".join(lines[1:]).rstrip()
                else:
                    body = "\n".join(lines).rstrip()
                if body:
                    code_map[target].append(body)
                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from heading '{heading}')")
                break
        else:
            still_unassigned.append(code)
    return still_unassigned, rescued_warnings