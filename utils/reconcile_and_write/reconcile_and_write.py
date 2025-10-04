from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
import logging

from fnmatch import fnmatch

from utils.safe_write_text.safe_write_text import safe_write_text
from utils.validate_entry_path.validate_entry_path import validate_entry_path
from utils.normalize_path_segment.normalize_path_segment import normalize_path_segment
from utils.is_probably_file.is_probably_file import is_probably_file
from utils.config.config import EXT_COMMENT_PLACEHOLDER, get_comment_prefix

def reconcile_and_write(
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    out_root: Path,
    dry_run: bool = False,
    verbose: bool = False,
    skip_empty: bool = False,
    ignore_patterns: Optional[List[str]] = None,
    files_always: Optional[Set] = None,
    dirs_always: Optional[Set] = None,
    no_overwrite: bool = False,
    heading_map: Dict[str, str] = {},
) -> Tuple[Set, List[str], List[str], int, int, int]:
    """
    Returns (created_dirs, created_files, warnings, total_lines_written, placeholders_created, files_written_count)
    """
    created_files: List[str] = []
    created_dirs: Set = set()
    warnings: List[str] = []
    ignore_patterns = ignore_patterns or []
    files_always = files_always or set()
    dirs_always = dirs_always or set()

    total_lines_written = 0
    placeholders_created = 0
    files_written_count = 0

    for entry in tree_entries:
        entry_clean = normalize_path_segment(entry)
        if not entry_clean:
            continue
        err = validate_entry_path(entry_clean)
        if err:
            warnings.append(f"❌ Unsafe path '{entry_clean}': {err}")
            continue
        if any(fnmatch(entry_clean, pat) for pat in ignore_patterns):
            continue
        parts = entry_clean.split("/")
        name = parts[-1]
        if is_probably_file(name, files_always, dirs_always):
            path = out_root.joinpath(*parts)
            content_parts = code_map.get(entry_clean, [])
            if content_parts:
                content = "\n\n".join(content_parts).strip() + "\n"
            else:
                ext = "." + name.split(".")[-1] if "." in name else ""
                content = EXT_COMMENT_PLACEHOLDER.get(ext, EXT_COMMENT_PLACEHOLDER["default"])
                placeholders_created += 1

            # Prepend heading as comment if available
            if entry_clean in heading_map:
                heading = heading_map[entry_clean]
                ext = Path(entry_clean).suffix.lower()
                prefix = get_comment_prefix(ext)
                if prefix:
                    prepended = prefix + heading
                    if prefix == "/* ":
                        prepended += " */"
                    elif prefix == "<!-- ":
                        prepended += " -->"
                    content = prepended + "\n" + content

            if skip_empty and (not content_parts):
                warnings.append(f"ℹ️ Skipped placeholder file {entry_clean} due to --skip-empty")
                continue
            if verbose:
                logging.debug(f"[write] {path}")
            if not dry_run:
                written = safe_write_text(path, content, warnings, no_overwrite=no_overwrite)
                if written:
                    files_written_count += 1
                    total_lines_written += content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            else:
                total_lines_written += content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            created_files.append(str(path))
        else:
            path = out_root.joinpath(*parts)
            if not dry_run:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    warnings.append(f"⚠️ Failed to create dir {path}: {e}")
            created_dirs.add(str(path))
    return created_dirs, created_files, warnings, total_lines_written, placeholders_created, files_written_count