from typing import List, Tuple, Dict
import re

def try_rescue_unassigned(
    unassigned: List[str],
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    strip_hints: bool,
) -> Tuple[List[str], List[str]]:
    rescued_warnings: List[str] = []
    still_unassigned: List[str] = []

    for code in unassigned:
        lines = code.splitlines()
        first_line = lines[0] if lines else ""
        if first_line.strip().startswith("//") or first_line.strip().startswith("#"):
            hint_path = re.sub(r"^(\s*//\s*|\s*#\s*)", "", first_line).strip().lstrip("./")
            candidates = []
            for f in code_map.keys():
                if f == hint_path:
                    candidates = [f]
                    break
                if f.endswith(hint_path):
                    candidates.append(f)
            if not candidates:
                candidates = [f for f in code_map.keys() if hint_path in f]
            if len(candidates) == 1:
                target = candidates[0]
                if strip_hints:
                    body = "\n".join(lines[1:]).rstrip()
                else:
                    body = "\n".join(lines).rstrip()
                if body:
                    code_map[target].append(body)
                rescued_warnings.append(f"ℹ️ Rescued block → assigned to {target} (from hint {hint_path})")
            elif len(candidates) > 1:
                rescued_warnings.append(f"⚠️ Ambiguous hint {hint_path} → matches {candidates}, kept unassigned")
                still_unassigned.append(code)
            else:
                rescued_warnings.append(f"⚠️ Hint {hint_path} did not match any file, kept unassigned")
                still_unassigned.append(code)
        else:
            still_unassigned.append(code)
    return still_unassigned, rescued_warnings