from typing import List, Optional
import sys
import logging

def resolve_conflict_interactive(hint: str, candidates: List[str]) -> Optional[str]:
    """
    Resolve ambiguous hint conflicts through interactive user input.
    
    Args:
        hint: The ambiguous hint that matched multiple files
        candidates: List of candidate file paths that matched the hint
        
    Returns:
        Selected file path or None if skipped/cancelled
    """
    # Input validation
    if not hint or not candidates:
        logging.warning("⚠️ Invalid input for conflict resolution")
        return None
    
    if len(candidates) == 1:
        return candidates[0]  # No conflict if only one candidate
    
    try:
        print(f"\n{'='*60}")
        print(f"⚠️  AMBIGUOUS HINT DETECTED")
        print(f"{'='*60}")
        print(f"Hint: '{hint}'")
        print(f"Matches {len(candidates)} files:")
        print("-" * 40)
        
        # Display candidates with clear numbering
        for idx, candidate in enumerate(candidates, 1):
            print(f"  {idx}. {candidate}")
        
        print("-" * 40)
        print("Options:")
        print("  [1-{0}]  - Select file by number".format(len(candidates)))
        print("  [s]     - Skip this file")
        print("  [a]     - Abort entire process")
        print("  [d]     - Display file differences (if available)")
        print("-" * 40)
        
        while True:
            try:
                choice = input("Choose an option: ").strip().lower()
                
                # Handle numeric selection
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(candidates):
                        selected = candidates[idx]
                        print(f"✅ Selected: {selected}")
                        return selected
                    else:
                        print(f"❌ Please enter a number between 1 and {len(candidates)}")
                
                # Handle skip option
                elif choice in ['s', 'skip', '']:
                    print("⏭️  Skipping this file")
                    return None
                
                # Handle abort option
                elif choice in ['a', 'abort', 'q', 'quit']:
                    print("🛑 Process aborted by user")
                    sys.exit(1)
                
                # Handle display differences option
                elif choice in ['d', 'diff']:
                    display_candidate_differences(candidates)
                
                # Handle help
                elif choice in ['h', 'help', '?']:
                    display_help_message()
                
                else:
                    print("❌ Invalid option. Please choose a valid option.")
                    
            except KeyboardInterrupt:
                print("\n🛑 Process interrupted by user")
                sys.exit(1)
            except EOFError:
                print("\n🛑 End of input reached")
                return None
            except Exception as e:
                print(f"❌ Error processing input: {e}")
                continue
                
    except Exception as e:
        logging.error(f"❌ Error in interactive conflict resolution: {e}")
        return None

def display_candidate_differences(candidates: List[str]) -> None:
    """
    Display differences between candidates to help user choose.
    
    Args:
        candidates: List of candidate file paths
    """
    print("\n📊 Candidate Analysis:")
    print("-" * 40)
    
    # Analyze path characteristics
    for i, candidate in enumerate(candidates, 1):
        path_parts = candidate.split('/')
        print(f"{i}. {candidate}")
        print(f"   Depth: {len(path_parts)}")
        print(f"   Directory: {'/'.join(path_parts[:-1]) or '(root)'}")
        print(f"   Filename: {path_parts[-1]}")
        
        # Show file extension if any
        if '.' in path_parts[-1]:
            ext = '.' + path_parts[-1].split('.')[-1]
            print(f"   Extension: {ext}")
        print()

def display_help_message() -> None:
    """
    Display help message for interactive conflict resolution.
    """
    print("\n📖 Help - Conflict Resolution:")
    print("=" * 50)
    print("When a hint matches multiple files, you need to choose:")
    print()
    print("• Enter a NUMBER to select that specific file")
    print("• Enter 's' to SKIP this file (it will be unassigned)")
    print("• Enter 'a' to ABORT the entire generation process")
    print("• Enter 'd' to see detailed DIFFERENCES between files")
    print("• Enter 'h' to see this HELP message again")
    print()
    print("Tip: Look at the file paths and choose the one that")
    print("     makes the most sense for your project structure.")
    print("=" * 50)

def resolve_conflict_batch(hint: str, candidates: List[str], strategy: str = "first") -> Optional[str]:
    """
    Resolve conflicts in batch mode without user interaction.
    
    Args:
        hint: The ambiguous hint
        candidates: List of candidate file paths
        strategy: Resolution strategy - "first", "longest", "shortest", "skip"
        
    Returns:
        Selected file path or None
    """
    if not candidates:
        return None
    
    if len(candidates) == 1:
        return candidates[0]
    
    logging.info(f"🔍 Batch conflict resolution for '{hint}': {len(candidates)} candidates")
    
    if strategy == "first":
        selected = candidates[0]
        logging.info(f"✅ Selected first candidate: {selected}")
        return selected
    
    elif strategy == "longest":
        selected = max(candidates, key=len)
        logging.info(f"✅ Selected longest path: {selected}")
        return selected
    
    elif strategy == "shortest":
        selected = min(candidates, key=len)
        logging.info(f"✅ Selected shortest path: {selected}")
        return selected
    
    elif strategy == "most_specific":
        # Prefer paths with more segments (deeper in hierarchy)
        selected = max(candidates, key=lambda x: len(x.split('/')))
        logging.info(f"✅ Selected most specific path: {selected}")
        return selected
    
    elif strategy == "skip":
        logging.info("⏭️  Skipping due to conflict")
        return None
    
    else:
        logging.warning(f"⚠️ Unknown batch strategy '{strategy}', using 'first'")
        return candidates[0]

def validate_candidate_selection(selected: str, original_candidates: List[str]) -> bool:
    """
    Validate that a selected candidate is from the original list.
    
    Args:
        selected: The selected candidate
        original_candidates: Original list of candidates
        
    Returns:
        True if selection is valid
    """
    return selected in original_candidates

# Utility function for testing
def mock_interactive_input(inputs: List[str]):
    """
    Mock function for testing interactive input.
    
    Args:
        inputs: List of input strings to simulate user responses
    """
    global input
    input_iter = iter(inputs)
    input = lambda prompt: next(input_iter)

def test_conflict_resolution():
    """
    Test function for conflict resolution.
    """
    test_cases = [
        ("utils", ["src/utils.py", "tests/utils.py", "utils/index.js"]),
        ("config", ["config.json", "src/config.py", "config/config.yaml"]),
        ("readme", ["README.md", "docs/README.md"]),
    ]
    
    print("Testing Conflict Resolution:")
    print("=" * 50)
    
    for hint, candidates in test_cases:
        print(f"\nTest: hint='{hint}', candidates={candidates}")
        
        # Test batch resolution
        for strategy in ["first", "longest", "shortest", "skip"]:
            result = resolve_conflict_batch(hint, candidates, strategy)
            print(f"  Batch '{strategy}': {result}")
        
        print("  Interactive: [simulated]")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    # Enable debug logging for testing
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    test_conflict_resolution()