from typing import List

def resolve_conflict_interactive(hint: str, candidates: List[str]) -> str | None:
    print(f"\n⚠️ Ambiguous hint '{hint}' matches multiple files:")
    for idx, c in enumerate(candidates, 1):
        print(f"  {idx}. {c}")
    choice = input("Choose target (number or Enter to skip): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    return None