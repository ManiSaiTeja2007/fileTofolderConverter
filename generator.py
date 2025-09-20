#!/usr/bin/env python3
"""
generator.py
Markdown → Project folder generator (Phase 1)

Adds:
- config file support (generator.config.json)
- preview mode (--preview)
- custom placeholders via JSON (--placeholders)
- safe-overwrite (--no-overwrite)
- path traversal guard (blocks absolute / .. escaping)
- additional stats in report/json
- tar.gz archiving (--tar)
- preserves previous behaviors: rescue hints, strip-hints, zip
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import tarfile
import textwrap
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from markdown_it import MarkdownIt
from markdown_it.token import Token

# -------------------------
# Default placeholders by extension
# -------------------------
EXT_COMMENT_PLACEHOLDER: Dict[str, str] = {
    ".py": "# TODO: implement\n",
    ".js": "// TODO: implement\n",
    ".ts": "// TODO: implement\n",
    ".tsx": "// TODO: implement\n",
    ".jsx": "// TODO: implement\n",
    ".java": "// TODO: implement\n",
    ".go": "// TODO: implement\n",
    ".rs": "// TODO: implement\n",
    ".sh": "# TODO: implement\n",
    ".yml": "# TODO: implement\n",
    ".yaml": "# TODO: implement\n",
    ".json": "{\n  // TODO: fill\n}\n",
    ".md": "<!-- TODO: fill -->\n",
    "default": "# TODO: implement\n",
}

# -------------------------
# File detection + special cases
# -------------------------
SPECIAL_FILES = {
    "dockerfile",
    "makefile",
    "license",
    "readme",
    "readme.md",
    "contributing",
    "authors",
    "changelog",
    ".gitignore",
    ".eslintrc",
    ".editorconfig",
    "firestore.rules",
    ".env",
    "tsconfig.json",
    "package.json",
    "requirements.txt",
    "procfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def is_probably_file(name: str, files_always: Optional[set] = None, dirs_always: Optional[set] = None) -> bool:
    """Heuristic to decide whether a segment is a file."""
    if not name:
        return False
    files_always = set(x.lower() for x in (files_always or set()))
    dirs_always = set(x.lower() for x in (dirs_always or set()))
    if name.endswith("/"):
        return False
    base = Path(name).name
    base_lower = base.lower()
    if base_lower in dirs_always:
        return False
    if base_lower in files_always or base_lower in SPECIAL_FILES:
        return True
    if base_lower == "dockerfile":
        return True
    return "." in base


def normalize_path_segment(seg: str) -> str:
    return seg.strip().rstrip("/").strip()


# -------------------------
# Utilities
# -------------------------
def safe_write_text(path: Path, content: str, warnings: List[str], no_overwrite: bool = False) -> bool:
    """
    Write text safely creating parent directories.
    Returns True if file was written, False if skipped or failed.
    Appends warnings on issues.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.is_dir():
                warnings.append(f"⚠️ Conflict: Tried to write file but a directory exists at {path}")
                return False
            if no_overwrite:
                warnings.append(f"ℹ️ Skipped existing file {path} due to --no-overwrite")
                return False
        if path.parent.exists() and path.parent.is_file():
            warnings.append(f"⚠️ Invalid structure: Parent is a file for {path}")
            return False
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        warnings.append(f"⚠️ Failed to write {path}: {e}")
        return False


# -------------------------
# Markdown parsing helpers
# -------------------------
def load_markdown(path: Path) -> Tuple[str, List[Token]]:
    md = MarkdownIt("commonmark")
    txt = path.read_text(encoding="utf-8")
    tokens = md.parse(txt)
    return txt, tokens


def extract_file_structure_block(md_text: str, tokens: List[Token]) -> Optional[str]:
    # Prefer token scanning
    for i, tok in enumerate(tokens):
        if tok.type == "inline" and "file structure" in tok.content.lower():
            j = i + 1
            while j < len(tokens):
                if tokens[j].type in ("fence", "code_block"):
                    return tokens[j].content
                if tokens[j].type == "heading_open":
                    break
                j += 1
    # fallback regex
    m = re.search(
        r"(?is)(?:^|\n)##+\s*File Structure\s*(?:\n+)(```(?:[\s\S]*?)```|(?:[\s\S]*?)(?=\n##|\Z))",
        md_text,
    )
    if m:
        block = m.group(1)
        if block.startswith("```"):
            return re.sub(r"^```[^\n]*\n([\s\S]*?)\n```$", r"\1", block, flags=re.I)
        return block
    return None


# -------------------------
# ASCII tree parsing (root handling, strip inline tags)
# -------------------------
def parse_ascii_tree_block(block_text: str, files_always: set, dirs_always: set) -> List[str]:
    lines = block_text.splitlines()
    entries: List[str] = []
    stack: List[Tuple[str, int]] = [("", 0)]

    for raw in lines:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" │"))
        # strip tree drawing chars at left and trailing slashes
        line = re.sub(r"^[\s│├└─]+", "", raw).rstrip("/")
        if not line:
            continue

        # strip inline comment/tags like '#edit', '#new'
        if line.strip().startswith("#"):
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        if " //" in line:
            line = line.split(" //", 1)[0].strip()
        if " -- " in line:
            line = line.split(" --", 1)[0].strip()

        if not line:
            continue

        while stack and indent <= stack[-1][1]:
            stack.pop()
        parent = stack[-1][0] if stack else ""
        full = f"{parent}/{line}" if parent else line
        entries.append(full)

        if not is_probably_file(line, files_always, dirs_always):
            stack.append((full, indent))

    # Root-folder fix: if the first entry is directory ensure others are its children
    if entries:
        root = entries[0]
        if not is_probably_file(Path(root).name, files_always, dirs_always):
            normalized: List[str] = []
            for e in entries[1:]:
                if e.startswith(root + "/"):
                    normalized.append(e)
                else:
                    normalized.append(f"{root}/{e}")
            return [root] + normalized
    return entries


# -------------------------
# Helper: infer target(s) from fence info string
# -------------------------
def infer_targets_from_fence_info(info: str, tree_entries: List[str]) -> List[str]:
    if not info:
        return []
    info_clean = info.strip().lower()
    candidates = []
    for f in tree_entries:
        base = Path(f).name.lower()
        if base == info_clean:
            candidates.append(f)
            continue
        if info_clean in base:
            candidates.append(f)
            continue
        if info_clean in f.lower():
            candidates.append(f)
    return candidates


# -------------------------
# Headings -> files mapping (captures paragraphs + fenced blocks)
# -------------------------
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

            # try first-line hint inside fence content
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
                # else fallthrough

            # try basename matching of fence_info
            if fence_info:
                fence_basename = Path(fence_info).name
                if fence_basename in basename_lookup and len(basename_lookup[fence_basename]) == 1:
                    code_map[basename_lookup[fence_basename][0]].append(fence_content)
                    warnings.append(
                        f"ℹ️ Assigned fenced block (basename '{fence_basename}') -> {basename_lookup[fence_basename][0]}"
                    )
                    i += 1
                    continue

            # fallback: unassigned
            unassigned.append(fence_content)
            i += 1
            continue

        # paragraph blocks
        if tok.type == "paragraph_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            para_text = ""
            if inline and inline.type == "inline":
                para_text = inline.content.strip()
            if current_file and current_file in code_map:
                if para_text:
                    code_map[current_file].append(para_text)
            # advance to paragraph_close
            j = i + 1
            while j < n and tokens[j].type != "paragraph_close":
                j += 1
            i = j + 1
            continue

        # default
        i += 1

    return code_map, unassigned, warnings


# -------------------------
# Rescue pass for remaining unassigned blocks (using first-line hints)
# -------------------------
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
            # ranking: exact match of full path > endswith match > contains
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


# -------------------------
# Extract project README content for non-file headings
# -------------------------
def extract_project_readme(tokens: List[Token], tree_entries: List[str]) -> str:
    file_names = {Path(f).name for f in tree_entries if is_probably_file(Path(f).name)}
    out_sections: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.type == "heading_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            if Path(heading_text).name in file_names or heading_text.strip().lower() == "file structure":
                i += 1
                continue
            section_lines: List[str] = [f"# {heading_text}" if not heading_text.startswith("#") else heading_text]
            i += 1
            while i < n and tokens[i].type != "heading_open":
                t = tokens[i]
                if t.type == "inline":
                    section_lines.append(t.content)
                elif t.type == "fence":
                    info = getattr(t, "info", "") or ""
                    fence_block = "```" + info + "\n" + t.content.rstrip() + "\n```"
                    section_lines.append(fence_block)
                elif t.type == "paragraph_open":
                    inlinep = tokens[i + 1] if (i + 1) < n else None
                    if inlinep and inlinep.type == "inline":
                        section_lines.append(inlinep.content)
                    j = i + 1
                    while j < n and tokens[j].type != "paragraph_close":
                        j += 1
                    i = j
                i += 1
            out_sections.append("\n\n".join(section_lines).strip())
            continue
        i += 1
    return "\n\n".join(out_sections).strip()


# -------------------------
# Reconcile & write to disk (with no-overwrite support and path validation)
# -------------------------
def validate_entry_path(entry: str) -> Optional[str]:
    """
    Return None if entry looks safe.
    Otherwise return an error string describing the problem.
    Rules:
    - No absolute paths (must not start with '/')
    - No parent traversal that escapes root ('..' as a segment)
    - No Windows drive-letter like 'C:\'
    """
    if not entry:
        return "Empty path"
    if entry.startswith("/") or entry.startswith("\\"):
        return "Absolute paths are not allowed"
    if ".." in Path(entry).parts:
        return "Parent traversal ('..') not allowed"
    # Windows drive detection
    if re.match(r"^[A-Za-z]:\\", entry):
        return "Absolute Windows paths not allowed"
    return None


def reconcile_and_write(
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    out_root: Path,
    dry_run: bool = False,
    verbose: bool = False,
    skip_empty: bool = False,
    ignore_patterns: Optional[List[str]] = None,
    files_always: Optional[set] = None,
    dirs_always: Optional[set] = None,
    no_overwrite: bool = False,
) -> Tuple[set, List[str], List[str], int, int, int]:
    """
    Returns (created_dirs, created_files, warnings, total_lines_written, placeholders_created, files_written_count)
    """
    created_files: List[str] = []
    created_dirs: set = set()
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
        # validate path safety
        err = validate_entry_path(entry_clean)
        if err:
            warnings.append(f"❌ Unsafe path '{entry_clean}': {err}")
            continue
        if any(fnmatch(entry_clean, pat) for pat in ignore_patterns):
            continue
        parts = entry_clean.split("/")
        name = parts[-1]
        # directory or file?
        if is_probably_file(name, files_always, dirs_always):
            path = out_root.joinpath(*parts)
            content_parts = code_map.get(entry_clean, [])
            if content_parts:
                content = "\n\n".join(content_parts).strip() + "\n"
            else:
                ext = "." + name.split(".")[-1] if "." in name else ""
                content = EXT_COMMENT_PLACEHOLDER.get(ext, EXT_COMMENT_PLACEHOLDER["default"])
                placeholders_created += 1
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
                # preview: count lines heuristically
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


# -------------------------
# Verification
# -------------------------
def verify_output(out_root: Path, tree_files: List[str], code_map: Dict[str, List[str]], warnings: List[str]):
    for f in tree_files:
        name = Path(f).name
        if not is_probably_file(name):
            continue
        path = out_root / f
        if not path.exists():
            warnings.append(f"❌ Missing file: {f}")
        else:
            try:
                size = path.stat().st_size
            except Exception:
                size = 0
            if size == 0:
                warnings.append(f"⚠️ Empty file: {f}")
            if len(code_map.get(f, [])) > 1:
                warnings.append(f"⚠️ File {f} had multiple code blocks merged")


# -------------------------
# Report writer (adds stats)
# -------------------------
def write_extension_report(
    out_root: Path,
    tree_entries: List[str],
    code_map: Dict[str, List[str]],
    unassigned: List[str],
    warnings: List[str],
    errors: List[str],
    report_path: Path,
    summary: dict,
    elapsed: float,
    rescued_warnings: List[str],
):
    lines: List[str] = []
    lines.append("# Generation Report")
    lines.append("")
    lines.append("## File Structure Status")
    lines.append("")
    lines.append("```text")
    for entry in tree_entries:
        parts = entry.split("/")
        depth = len(parts) - 1
        prefix = ("│   " * (depth - 1)) + ("├── " if depth > 0 else "")
        name = parts[-1]
        path = out_root / entry
        if path.exists() and path.is_dir():
            lines.append(f"{prefix}{name}/")
        else:
            if not path.exists():
                lines.append(f"{prefix}{name} ❌ MISSING")
            else:
                try:
                    content = path.read_text(encoding="utf-8").strip()
                except Exception:
                    content = ""
                if not content or content.startswith(("# TODO", "// TODO", "<!-- TODO")):
                    lines.append(f"{prefix}{name} ⚠️ placeholder")
                else:
                    lines.append(f"{prefix}{name} ✅")
    lines.append("```")
    if errors or warnings or rescued_warnings:
        lines.append("\n## Issues")
        if errors:
            lines.append("### Errors")
            for e in errors:
                lines.append(f"- ❌ {e}")
        if warnings:
            lines.append("### Warnings")
            for w in warnings:
                lines.append(f"- ⚠️ {w}")
        if rescued_warnings:
            lines.append("### Rescued / Mapping Notes")
            for r in rescued_warnings:
                lines.append(f"- ℹ️ {r}")
    else:
        lines.append("\n## Issues\n✅ None")

    if unassigned:
        lines.append("\n## Unassigned Blocks")
        lines.append(f"- {len(unassigned)} saved in `UNASSIGNED/`")
    else:
        lines.append("\n## Unassigned Blocks\n✅ None")

    lines.append("\n## Completed Summary")
    lines.append(f"- Files in tree: {summary.get('files_in_tree', 0)}")
    lines.append(f"- Files created: {summary.get('files_created', 0)}")
    lines.append(f"- Dirs created: {summary.get('dirs_created', 0)}")
    lines.append(f"- Unassigned blocks: {summary.get('unassigned_blocks', 0)}")
    lines.append(f"- Issues: {len(warnings) + len(errors)}")
    lines.append(f"- Time taken: {elapsed:.2f}s")
    lines.append(f"- Lines written (approx): {summary.get('lines_written', 0)}")
    lines.append(f"- Placeholder-only files: {summary.get('placeholders_created', 0)}")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


# -------------------------
# Config loading / merging
# -------------------------
def load_config_file(explicit_path: Optional[str] = None) -> dict:
    """
    Load configuration JSON from:
      - explicit_path (if provided)
      - ./generator.config.json
      - <script_dir>/generator.config.json
    Returns empty dict if none found or parse error.
    """
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    candidates.append(Path.cwd() / "generator.config.json")
    script_dir = Path(__file__).parent if "__file__" in globals() else Path.cwd()
    candidates.append(script_dir / "generator.config.json")

    for p in candidates:
        try:
            if p and p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            # ignore parse errors for now
            continue
    return {}


def merge_placeholders_from_file(placeholders_path: Optional[str]):
    """If provided, merge external JSON placeholders into EXT_COMMENT_PLACEHOLDER."""
    global EXT_COMMENT_PLACEHOLDER
    if not placeholders_path:
        return
    p = Path(placeholders_path)
    if not p.exists():
        logging.warning(f"⚠️ Placeholders file not found: {placeholders_path}")
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for k, v in data.items():
                EXT_COMMENT_PLACEHOLDER[k] = v
            logging.info(f"ℹ️ Loaded placeholders from {placeholders_path}")
        else:
            logging.warning("⚠️ Placeholders file must contain a JSON object mapping extensions to text.")
    except Exception as e:
        logging.warning(f"⚠️ Failed to load placeholders: {e}")


# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate project folder from Markdown spec")
    parser.add_argument("input", help="Markdown file path")
    parser.add_argument("-o", "--output", default="output_folder", help="Output folder (default: output_folder)")

    # Core flags
    parser.add_argument("--strict", action="store_true", help="Abort on errors")
    parser.add_argument("--dry", action="store_true", help="Dry run (no writing)")
    parser.add_argument("--preview", action="store_true", help="Preview planned tree and assignments (no writing)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet (errors only)")
    parser.add_argument("--debug", action="store_true", help="Debug logging")

    # File creation
    parser.add_argument("--skip-empty", action="store_true", help="Do not create placeholder-only files")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing files")

    # Config & overrides
    parser.add_argument("--json-summary", metavar="FILE", help="Write JSON summary to FILE")
    parser.add_argument("--ignore", nargs="*", default=[], help="Glob patterns to ignore (e.g. '*.md')")
    parser.add_argument("--files-always", nargs="*", default=[], help="Names to always treat as files")
    parser.add_argument("--dirs-always", nargs="*", default=[], help="Names to always treat as dirs")
    parser.add_argument("--placeholders", metavar="FILE", help="JSON file with placeholder overrides")
    parser.add_argument("--config", metavar="FILE", help="Path to generator.config.json to load defaults")

    # Advanced features
    parser.add_argument("--strip-hints", action="store_true", help="Strip first-line hint comments from rescued content")
    parser.add_argument("--zip", action="store_true", help="Zip the output folder after generation")
    parser.add_argument("--tar", action="store_true", help="Tar.gz the output folder after generation")

    # Phase 2 (generator_extras)
    parser.add_argument("--interactive", action="store_true", help="Prompt user when conflicts occur")
    parser.add_argument("--html-report", metavar="FILE", nargs="?", const="report.html", default=None, help="Write HTML interactive report (default if used without filename: %(const)s)")    
    parser.add_argument("--incremental", action="store_true", help="Only regenerate changed files")
    parser.add_argument("--set-exec", action="store_true", help="Set executable flag on *.sh and Procfile/Makefile")
    parser.add_argument("--export-md", metavar="FILE", help="Export generated project back into Markdown")
    parser.add_argument("--extension-report", metavar="FILE",help="Custom report file (default: report.md)")

    args = parser.parse_args()

    # -------------------------
    # Load config & merge
    # -------------------------
    cfg = load_config_file(args.config)

    def merge_flag(name, current, expected_type=None):
        if current not in (None, [], False, "output_folder"):
            return current
        if name in cfg:
            return cfg[name]
        return current

    args.output = merge_flag("output", args.output)
    args.ignore = merge_flag("ignore", args.ignore)
    args.files_always = merge_flag("files_always", args.files_always)
    args.dirs_always = merge_flag("dirs_always", args.dirs_always)
    args.placeholders = merge_flag("placeholders", args.placeholders)
    args.strip_hints = merge_flag("strip_hints", args.strip_hints, bool)
    args.zip = merge_flag("zip", args.zip, bool)
    args.tar = merge_flag("tar", args.tar, bool)
    args.no_overwrite = merge_flag("no_overwrite", args.no_overwrite, bool)

    # -------------------------
    # Logging setup
    # -------------------------
    if args.debug:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    # -------------------------
    # Placeholders merging
    # -------------------------
    merge_placeholders_from_file(args.placeholders)

    # -------------------------
    # Load input markdown
    # -------------------------
    start = time.time()
    in_path = Path(args.input)
    if not in_path.exists():
        logging.error(f"❌ Input file not found: {in_path}")
        sys.exit(2)

    md_text, tokens = load_markdown(in_path)
    fs_block = extract_file_structure_block(md_text, tokens)
    if not fs_block:
        logging.error("❌ Could not find a 'File Structure' block in the markdown.")
        sys.exit(3)

    files_always = set(args.files_always)
    dirs_always = set(args.dirs_always)

    tree_entries = parse_ascii_tree_block(fs_block, files_always, dirs_always)
    code_map, unassigned, mapping_warnings = map_headings_to_files(
        tokens, tree_entries, files_always, dirs_always, strip_hints=args.strip_hints
    )
    unassigned, rescue_warnings = try_rescue_unassigned(unassigned, tree_entries, code_map, strip_hints=args.strip_hints)

    all_warnings = mapping_warnings + rescue_warnings
    errors = []

    # -------------------------
    # Preview mode
    # -------------------------
    if args.preview:
        print("\n---- Preview: Planned file assignments ----\n")
        for f in tree_entries:
            if is_probably_file(Path(f).name, files_always, dirs_always):
                assigned = code_map.get(f, [])
                status = "placeholder" if not assigned else "assigned"
                print(f"{f} -> {status} ({len(assigned)} block(s))")
            else:
                print(f"{f}/")
        if unassigned:
            print(f"\nUnassigned blocks: {len(unassigned)}")
        else:
            print("\nNo unassigned blocks.")
        if args.json_summary:
            with open(args.json_summary, "w", encoding="utf-8") as jf:
                json.dump({"files_in_tree": len([f for f in tree_entries if is_probably_file(Path(f).name, files_always, dirs_always)]),
                           "unassigned_blocks": len(unassigned)}, jf, indent=2)
        return

    # -------------------------
    # Prepare output
    # -------------------------
    out_root = Path(args.output)
    if out_root.exists() and not args.dry and not args.no_overwrite:
        shutil.rmtree(out_root)

    created_dirs, created_files, write_warnings, total_lines_written, placeholders_created, files_written_count = reconcile_and_write(
        tree_entries, code_map, out_root,
        dry_run=args.dry, verbose=args.verbose, skip_empty=args.skip_empty,
        ignore_patterns=args.ignore, files_always=files_always, dirs_always=dirs_always,
        no_overwrite=args.no_overwrite
    )

    if unassigned and not args.dry:
        un_dir = out_root / "UNASSIGNED"
        un_dir.mkdir(parents=True, exist_ok=True)
        for i, block in enumerate(unassigned, 1):
            (un_dir / f"unassigned_{i}.txt").write_text(block, encoding="utf-8")

    verify_output(out_root, tree_entries, code_map, write_warnings)

    elapsed = time.time() - start
    summary = {
        "files_in_tree": len([f for f in tree_entries if is_probably_file(Path(f).name, files_always, dirs_always)]),
        "files_created": len(created_files),
        "dirs_created": len(created_dirs),
        "unassigned_blocks": len(unassigned),
        "issues": write_warnings + all_warnings,
        "lines_written": total_lines_written,
        "placeholders_created": placeholders_created,
        "files_written_count": files_written_count,
    }

    # -------------------------
    # Reports
    # -------------------------
    if args.json_summary:
        with open(args.json_summary, "w", encoding="utf-8") as jf:
            json.dump(summary, jf, indent=2)

    report_path = Path(args.extension_report) if args.extension_report else (out_root / "report.md")
    write_extension_report(out_root, tree_entries, code_map, unassigned,
                           write_warnings + all_warnings, errors, report_path,
                           summary, elapsed, rescue_warnings)

    project_readme = extract_project_readme(tokens, tree_entries)
    if project_readme and not args.dry:
        project_readme_path = out_root / "README.md"
        with open(project_readme_path, "a" if project_readme_path.exists() else "w", encoding="utf-8") as f:
            f.write("\n\n" + project_readme)

    # -------------------------
    # Archives
    # -------------------------
    if args.zip and not args.dry:
        shutil.make_archive(str(out_root), "zip", root_dir=out_root)
    if args.tar and not args.dry:
        import tarfile
        with tarfile.open(str(out_root) + ".tar.gz", "w:gz") as tar:
            tar.add(out_root, arcname=out_root.name)

    # -------------------------
    # Phase 2 delegation
    # -------------------------
    try:
        import extras.generator_extras as gx
    except ImportError:
        gx = None


    if args.interactive:
        # Replace ambiguous resolution logic with gx.resolve_conflict_interactive inside map_headings_to_files
        logging.info("ℹ️ Interactive conflict resolution enabled")

    if args.html_report:
        args.html_report = Path(args.output) / Path(args.html_report).name

    if args.export_md:
        args.export_md = Path(args.output) / Path(args.export_md).name

    if args.extension_report:
        args.extension_report = Path(args.output) / Path(args.extension_report).name
        
    if gx and args.html_report:
        gx.write_html_report(tree_entries, out_root, summary, Path(args.html_report))


    if args.incremental:
        cache_file = out_root / ".generator_cache.json"
        cache = gx.load_cache(cache_file)
        gx.save_cache(cache_file, cache)

    if args.set_exec:
        for f in created_files:
            if f.endswith(".sh") or Path(f).name in ("Procfile", "Makefile"):
                gx.set_executable(Path(f))

    if args.export_md:
        gx.export_to_markdown(out_root, Path(args.export_md))

    # -------------------------
    # Final console summary
    # -------------------------
    if level <= logging.INFO:
        logging.info("\n---- Final Report ----")
        for k, v in summary.items():
            logging.info(f"{k}: {v}")
        if summary["unassigned_blocks"]:
            logging.warning(f"⚠️ {summary['unassigned_blocks']} unassigned block(s) saved in UNASSIGNED/")
        elif not summary["issues"]:
            logging.info("✅ All files created and verified successfully")



if __name__ == "__main__":
    main()
