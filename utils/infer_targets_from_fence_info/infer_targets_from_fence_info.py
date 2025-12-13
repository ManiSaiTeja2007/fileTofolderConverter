from typing import List, Set, Optional
from pathlib import Path
import logging
import re
from functools import lru_cache

def normalize_string(text: str) -> str:
    """
    Normalize string for comparison by lowercasing and removing extra spaces.
    
    Args:
        text: Input string to normalize
        
    Returns:
        Normalized string
    """
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.strip().lower())

@lru_cache(maxsize=100)
def get_filename_variations(filename: str) -> Set[str]:
    """
    Generate common filename variations for fuzzy matching.
    
    Args:
        filename: Original filename
        
    Returns:
        Set of filename variations
    """
    variations = set()
    name_lower = filename.lower()
    
    # Basic variations
    variations.add(name_lower)
    variations.add(name_lower.replace('_', '').replace('-', ''))
    variations.add(name_lower.replace('_', '-'))
    variations.add(name_lower.replace('-', '_'))
    
    # Remove common extensions for matching
    for ext in ['.py', '.js', '.ts', '.json', '.md', '.txt', '.yml', '.yaml', '.xml', '.html', '.css']:
        if name_lower.endswith(ext):
            variations.add(name_lower[:-len(ext)])
    
    return variations

def exact_match_candidates(info_clean: str, tree_entries: List[str]) -> List[str]:
    """
    Find exact match candidates.
    
    Args:
        info_clean: Normalized fence info
        tree_entries: List of file paths
        
    Returns:
        List of exact match candidates
    """
    candidates = []
    
    for file_path in tree_entries:
        path = Path(file_path)
        
        # Exact filename match
        if path.name.lower() == info_clean:
            candidates.append(file_path)
            continue
            
        # Exact path match (without extension considerations)
        if file_path.lower() == info_clean:
            candidates.append(file_path)
    
    return candidates

def partial_match_candidates(info_clean: str, tree_entries: List[str]) -> List[str]:
    """
    Find partial match candidates with scoring.
    
    Args:
        info_clean: Normalized fence info
        tree_entries: List of file paths
        
    Returns:
        List of partial match candidates with scores
    """
    scored_candidates = []
    
    for file_path in tree_entries:
        path = Path(file_path)
        filename_lower = path.name.lower()
        filepath_lower = file_path.lower()
        
        score = 0
        
        # High score: info is contained in filename
        if info_clean in filename_lower:
            score += 3
            
            # Bonus: info matches start of filename
            if filename_lower.startswith(info_clean):
                score += 2
                
            # Bonus: exact match with different extension
            name_without_ext = path.stem.lower()
            if name_without_ext == info_clean:
                score += 2
        
        # Medium score: info is contained in full path
        elif info_clean in filepath_lower:
            score += 1
            
            # Bonus: info matches directory name
            for parent in path.parents:
                if parent.name.lower() == info_clean:
                    score += 1
                    break
        
        # Check filename variations
        filename_variations = get_filename_variations(path.name)
        if info_clean in filename_variations:
            score += 2
        
        if score > 0:
            scored_candidates.append((file_path, score))
    
    # Sort by score descending
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    return [candidate for candidate, score in scored_candidates]

def validate_candidates(candidates: List[str], info_clean: str) -> List[str]:
    """
    Validate and filter candidates.
    
    Args:
        candidates: List of candidate file paths
        info_clean: Original fence info for context
        
    Returns:
        Validated and filtered candidates
    """
    if not candidates:
        return []
    
    valid_candidates = []
    
    for candidate in candidates:
        path = Path(candidate)
        
        # Skip directories (unless they match exactly and are meaningful)
        if path.suffix == '' and len(candidates) > 1:
            # Only include directories if they're the only match or have high relevance
            continue
            
        valid_candidates.append(candidate)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_candidates = []
    for candidate in valid_candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)
    
    return unique_candidates

def infer_targets_from_fence_info(info: str, tree_entries: List[str]) -> List[str]:
    """
    Infer target file paths from code fence info string using multi-level matching.
    
    Args:
        info: Code fence info string (e.g., "python src/main.py")
        tree_entries: List of available file paths in the project
        
    Returns:
        List of inferred target file paths, ordered by match confidence
    """
    # Input validation
    if not info or not tree_entries:
        return []
    
    if not isinstance(info, str) or not isinstance(tree_entries, list):
        logging.warning("⚠️ Invalid input types for fence info inference")
        return []
    
    try:
        info_clean = normalize_string(info)
        logging.debug(f"🔍 Inferring targets from fence info: '{info}' -> '{info_clean}'")
        
        if not info_clean:
            return []
        
        # Step 1: Exact matches (highest confidence)
        exact_matches = exact_match_candidates(info_clean, tree_entries)
        if exact_matches:
            logging.debug(f"✅ Found {len(exact_matches)} exact matches: {exact_matches}")
            return validate_candidates(exact_matches, info_clean)
        
        # Step 2: Partial matches with scoring
        partial_matches = partial_match_candidates(info_clean, tree_entries)
        if partial_matches:
            logging.debug(f"✅ Found {len(partial_matches)} partial matches: {partial_matches}")
            return validate_candidates(partial_matches, info_clean)
        
        # Step 3: Try splitting info for complex cases (e.g., "python src/main.py")
        if ' ' in info_clean:
            parts = info_clean.split()
            for part in parts:
                if len(part) > 2:  # Only consider meaningful parts
                    part_matches = infer_targets_from_fence_info(part, tree_entries)
                    if part_matches:
                        logging.debug(f"✅ Found {len(part_matches)} matches from split part '{part}': {part_matches}")
                        return validate_candidates(part_matches, info_clean)
        
        logging.debug(f"❌ No matches found for fence info: '{info}'")
        return []
        
    except Exception as e:
        logging.error(f"❌ Error inferring targets from fence info '{info}': {e}")
        return []

# Alternative function with configurable matching strategy
def infer_targets_advanced(info: str, tree_entries: List[str], 
                          strategy: str = "balanced") -> List[str]:
    """
    Advanced target inference with configurable matching strategy.
    
    Args:
        info: Code fence info string
        tree_entries: List of available file paths
        strategy: Matching strategy - "strict", "balanced", or "aggressive"
        
    Returns:
        List of inferred target file paths
    """
    if strategy == "strict":
        # Only exact matches
        info_clean = normalize_string(info)
        return exact_match_candidates(info_clean, tree_entries)
    
    elif strategy == "balanced":
        # Default balanced approach
        return infer_targets_from_fence_info(info, tree_entries)
    
    elif strategy == "aggressive":
        # More permissive matching
        info_clean = normalize_string(info)
        candidates = []
        
        for file_path in tree_entries:
            path = Path(file_path)
            filename_lower = path.name.lower()
            filepath_lower = file_path.lower()
            
            # Very permissive matching
            if (info_clean in filename_lower or 
                info_clean in filepath_lower or
                any(variation in info_clean for variation in get_filename_variations(path.name))):
                candidates.append(file_path)
        
        return validate_candidates(candidates, info_clean)
    
    else:
        logging.warning(f"⚠️ Unknown strategy '{strategy}', using balanced")
        return infer_targets_from_fence_info(info, tree_entries)

# Utility function for debugging
def debug_fence_inference(info: str, tree_entries: List[str]) -> dict:
    """
    Debug function to analyze fence info inference process.
    
    Args:
        info: Fence info string
        tree_entries: List of file paths
        
    Returns:
        Dictionary with debug information
    """
    debug_info = {
        "input_info": info,
        "normalized_info": normalize_string(info) if info else "",
        "tree_entries_count": len(tree_entries),
        "exact_matches": [],
        "partial_matches": [],
        "final_candidates": [],
        "matching_strategy": "standard"
    }
    
    if info and tree_entries:
        info_clean = normalize_string(info)
        debug_info["exact_matches"] = exact_match_candidates(info_clean, tree_entries)
        debug_info["partial_matches"] = partial_match_candidates(info_clean, tree_entries)
        debug_info["final_candidates"] = infer_targets_from_fence_info(info, tree_entries)
    
    return debug_info