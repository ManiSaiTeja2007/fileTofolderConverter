#!/usr/bin/env python3
"""
generator.py
Markdown → Project folder generator (updated)

Features/highlights in this version:
- Maps headings -> files, captures fenced code + paragraphs for files
- Recognizes fenced info strings like ```dockerfile```, ```firestore.rules```
- Uses first-line hint comments (// path/to/file or # path/to/file) to reassign blocks
- Optionally strips those hint lines from written files via --strip-hints
- Improved SPECIAL_FILES and case-insensitive checks (Dockerfile, firestore.rules, .env, etc.)
- Skips the 'File Structure' fenced block from mapping
- Writes report.md (tree + issues + rescued notes + summary + elapsed time)
- Dumps non-file sections into generated project's README.md
- Supports flags: --skip-empty, --json-summary, --ignore, --files-always, --dirs-always,
  --extension-report, --dry, --verbose, --debug, -q, --strip-hints, --zip
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import textwrap
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from markdown_it import MarkdownIt
from markdown_it.token import Token

# -------------------------
# Placeholders by extension
# -------------------------
EXT_COMMENT_PLACEHOLDER = {
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
    "dockerfile", "makefile", "license", "readme", "readme.md",
    "contributing", "authors", "changelog", ".gitignore",
    ".eslintrc", ".editorconfig", "firestore.rules", ".env",
    "tsconfig.json", "package.json", "requirements.txt", "procfile",
    "docker-compose.yml", "docker-compose.yaml",
}


def is_probably_file(name: str, files_always: Optional[set] = None, dirs_always: Optional[set] = None) -> bool:
    """
    Decide whether a path segment is a file.
    - trailing '/' => directory
    - dirs_always override => directory
    - files_always or SPECIAL_FILES => file (case-insensitive)
    - special-case Dockerfile
    - else if contains '.' => file
    """
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
def safe_write_text(path: Path, content: str, warnings: List[str]):
    """Write text safely creating parent directories. Append warnings on errors."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.is_dir():
            warnings.append(f"⚠️ Conflict: Tried to write file but a directory exists at {path}")
            return
        if path.parent.exists() and path.parent.is_file():
            warnings.append(f"⚠️ Invalid structure: Parent is a file for {path}")
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        warnings.append(f"⚠️ Failed to write {path}: {e}")


# -------------------------
# Markdown parsing helpers
# -------------------------
def load_markdown(path: Path) -> Tuple[str, List[Token]]:
    md = MarkdownIt("commonmark")
    txt = path.read_text(encoding="utf-8")
    tokens = md.parse(txt)
    return txt, tokens


def extract_file_structure_block(md_text: str, tokens: List[Token]) -> Optional[str]:
    # Prefer scanning tokens for a heading that contains "file structure"
    for i, tok in enumerate(tokens):
        if tok.type == "inline" and "file structure" in tok.content.lower():
            # the fenced block should be shortly after
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

        # --- strip inline comment/tags like '#edit', '#new' ---
        # If the whole line starts with '#', ignore
        if line.strip().startswith("#"):
            continue
        # Remove trailing tags like "filename #edit #todo" -> "filename"
        if " #" in line:
            line = line.split(" #", 1)[0].strip()
        # Also remove trailing inline comments starting with '//' or '--'
        # e.g. "file.py // note" -> "file.py"
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

        # push as directory if heuristic says so
        if not is_probably_file(line, files_always, dirs_always):
            stack.append((full, indent))

    # Root-folder fix: if the first entry is a directory, ensure others are children
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
    """
    Use the fence info string (like 'dockerfile', 'firestore.rules', 'python') as hint
    to find candidate file paths in tree_entries (case-insensitive).
    """
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
    """
    Walk tokens and:
    - when a heading matches a file in tree_files, set current_file
    - capture paragraph text and fence blocks under that heading as file content
    - if a fence block appears without a mapped heading, attempt to infer target via:
        1) fence info string (e.g. ```dockerfile```)
        2) first-line hint comment (// path/to/file or # path/to/file)
        3) basename matching
    Returns (code_map, unassigned_blocks, mapping_warnings)
    """
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

        # --- heading handling ---
        if tok.type == "heading_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            heading_text_stripped = heading_text.strip()
            # Skip mapping for the File Structure heading (and skip its fence block)
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

        # --- fenced code block handling ---
        if tok.type == "fence":
            fence_info = getattr(tok, "info", "") or ""
            fence_info = fence_info.strip()
            fence_content = textwrap.dedent(tok.content).rstrip()

            # If this fence follows a "File Structure" heading, skip it (that's the ASCII tree)
            if skip_next_fence_for_file_structure:
                skip_next_fence_for_file_structure = False
                i += 1
                continue

            # If we have a current file (heading matched a file), attach to it
            if current_file and current_file in code_map:
                code_map[current_file].append(fence_content)
                i += 1
                continue

            # 1) Try to infer from fence info string
            candidates = infer_targets_from_fence_info(fence_info, list(code_map.keys()))
            if len(candidates) == 1:
                code_map[candidates[0]].append(fence_content)
                warnings.append(f"ℹ️ Assigned fenced block (info='{fence_info}') -> {candidates[0]}")
                i += 1
                continue
            elif len(candidates) > 1:
                warnings.append(
                    f"⚠️ Ambiguous fence info '{fence_info}' matches {candidates}; kept unassigned"
                )
                unassigned.append(fence_content)
                i += 1
                continue

            # 2) Try first-line hint inside fenced content (// or #)
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
                # else continue to other heuristics

            # 3) Try basename match of fence_info (e.g., fence_info="Dockerfile")
            if fence_info:
                fence_basename = Path(fence_info).name
                if fence_basename in basename_lookup and len(basename_lookup[fence_basename]) == 1:
                    code_map[basename_lookup[fence_basename][0]].append(fence_content)
                    warnings.append(
                        f"ℹ️ Assigned fenced block (basename '{fence_basename}') -> {basename_lookup[fence_basename][0]}"
                    )
                    i += 1
                    continue

            # None matched -> keep unassigned
            unassigned.append(fence_content)
            i += 1
            continue

        # --- paragraph blocks (map paragraph text under matching heading to files) ---
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

        # default advance
        i += 1

    return code_map, unassigned, warnings


# -------------------------
# Rescue pass for remaining unassigned blocks (first-line hints)
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
            candidates = [f for f in tree_entries if f.endswith(hint_path) or hint_path in f]
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
                rescued_warnings.append(
                    f"⚠️ Ambiguous hint {hint_path} → matches {candidates}, kept unassigned"
                )
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
    """
    Collect heading sections that don't map to files in the tree and return a Markdown string
    to be appended to the generated project's README.md.
    """
    file_names = {Path(f).name for f in tree_entries if is_probably_file(Path(f).name)}
    out_sections: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.type == "heading_open":
            inline = tokens[i + 1] if (i + 1) < n else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            # skip file-like headings and the File Structure heading
            if Path(heading_text).name in file_names or heading_text.strip().lower() == "file structure":
                i += 1
                continue
            section_lines: List[str] = [f"# {heading_text}" if not heading_text.startswith("#") else heading_text]
            i += 1
            # gather tokens until next heading_open
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
                    # advance to paragraph_close
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
# Reconcile & write to disk
# -------------------------
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
) -> Tuple[set, List[str], List[str]]:
    created_files: List[str] = []
    created_dirs: set = set()
    warnings: List[str] = []
    ignore_patterns = ignore_patterns or []
    files_always = files_always or set()
    dirs_always = dirs_always or set()

    for entry in tree_entries:
        entry_clean = normalize_path_segment(entry)
        if not entry_clean:
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
            if skip_empty and (not content_parts):
                warnings.append(f"ℹ️ Skipped placeholder file {entry_clean} due to --skip-empty")
                continue
            if verbose:
                logging.debug(f"[write] {path}")
            if not dry_run:
                safe_write_text(path, content, warnings)
            created_files.append(str(path))
        else:
            path = out_root.joinpath(*parts)
            if not dry_run:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    warnings.append(f"⚠️ Failed to create dir {path}: {e}")
            created_dirs.add(str(path))
    return created_dirs, created_files, warnings


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
            size = path.stat().st_size
            if size == 0:
                warnings.append(f"⚠️ Empty file: {f}")
            if len(code_map.get(f, [])) > 1:
                warnings.append(f"⚠️ File {f} had multiple code blocks merged")


# -------------------------
# Report writer
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
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


# -------------------------
# Main
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate project folder from Markdown spec")
    parser.add_argument("input", help="Markdown file path")
    parser.add_argument("-o", "--output", default="output_folder", help="Output folder")
    parser.add_argument("--strict", action="store_true", help="Abort on errors")
    parser.add_argument("--dry", action="store_true", help="Dry run (no writing)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet (errors only)")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    parser.add_argument("--skip-empty", action="store_true", help="Do not create placeholder-only files")
    parser.add_argument("--json-summary", metavar="FILE", help="Write JSON summary to FILE")
    parser.add_argument("--ignore", nargs="*", default=[], help="Glob patterns to ignore (e.g. '*.md')")
    parser.add_argument("--files-always", nargs="*", default=[], help="Names to always treat as files")
    parser.add_argument("--dirs-always", nargs="*", default=[], help="Names to always treat as dirs")
    parser.add_argument("--extension-report", metavar="FILE", help="Write audit report (default: report.md in output)")
    parser.add_argument("--strip-hints", action="store_true", help="Strip first-line hint comments from rescued content")
    parser.add_argument("--zip", action="store_true", help="Zip the output folder after generation")
    args = parser.parse_args()

    # logging level
    if args.debug:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

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

    # parse tree
    tree_entries = parse_ascii_tree_block(fs_block, files_always, dirs_always)

    # map headings -> files (captures paragraphs + fenced blocks)
    code_map, unassigned, mapping_warnings = map_headings_to_files(
        tokens, tree_entries, files_always, dirs_always, strip_hints=args.strip_hints
    )

    # final rescue pass for remaining unassigned using first-line hints
    unassigned, rescue_warnings = try_rescue_unassigned(unassigned, tree_entries, code_map, strip_hints=args.strip_hints)

    # aggregate warnings/errors
    all_warnings: List[str] = mapping_warnings[:]
    all_warnings.extend(rescue_warnings)
    errors: List[str] = []
    # optional strict behavior
    if errors and args.strict:
        logging.error("❌ Strict mode: aborting due to errors.")
        sys.exit(1)

    # prepare output
    out_root = Path(args.output)
    if out_root.exists() and not args.dry:
        shutil.rmtree(out_root)

    created_dirs, created_files, write_warnings = reconcile_and_write(
        tree_entries,
        code_map,
        out_root,
        dry_run=args.dry,
        verbose=args.verbose,
        skip_empty=args.skip_empty,
        ignore_patterns=args.ignore,
        files_always=files_always,
        dirs_always=dirs_always,
    )

    # write unassigned files into UNASSIGNED/
    if unassigned and not args.dry:
        un_dir = out_root / "UNASSIGNED"
        un_dir.mkdir(parents=True, exist_ok=True)
        for i, block in enumerate(unassigned, 1):
            (un_dir / f"unassigned_{i}.txt").write_text(block, encoding="utf-8")

    # verification (adds to write_warnings)
    verify_output(out_root, tree_entries, code_map, write_warnings)

    elapsed = time.time() - start
    summary = {
        "files_in_tree": len([f for f in tree_entries if is_probably_file(Path(f).name, files_always, dirs_always)]),
        "files_created": len(created_files),
        "dirs_created": len(created_dirs),
        "unassigned_blocks": len(unassigned),
        "issues": write_warnings + all_warnings,
    }

    # json summary if requested
    if args.json_summary:
        with open(args.json_summary, "w", encoding="utf-8") as jf:
            json.dump(summary, jf, indent=2)

    # write report (default to report.md inside output root)
    report_path = Path(args.extension_report) if args.extension_report else (out_root / "report.md")
    write_extension_report(out_root, tree_entries, code_map, unassigned, write_warnings + all_warnings, errors, report_path, summary, elapsed, rescue_warnings)

    # populate generated project's README.md with non-file sections
    project_readme = extract_project_readme(tokens, tree_entries)
    if project_readme and not args.dry:
        project_readme_path = out_root / "README.md"
        mode = "a" if project_readme_path.exists() else "w"
        with open(project_readme_path, mode, encoding="utf-8") as f:
            f.write("\n\n" + project_readme)

    # zip output if requested (skip in dry)
    if args.zip and not args.dry:
        try:
            archive_path = shutil.make_archive(str(out_root), "zip", root_dir=out_root)
            logging.info(f"📦 Zipped project folder at {archive_path}")
        except Exception as e:
            logging.warning(f"⚠️ Failed to zip output folder: {e}")

    # final console output unless quiet
    if level <= logging.INFO:
        logging.info("\n---- Final Report ----")
        logging.info(f"📄 Files in tree: {summary['files_in_tree']}")
        logging.info(f"📄 Files created: {summary['files_created']}")
        logging.info(f"📁 Dirs created: {summary['dirs_created']}")
        if summary["issues"]:
            logging.warning("\n⚠️ Issues:")
            for w in summary["issues"]:
                logging.warning(" - " + w)
        else:
            logging.info("✅ All files created and verified successfully")
        if summary["unassigned_blocks"]:
            logging.warning(f"⚠️ {summary['unassigned_blocks']} unassigned code block(s) saved in UNASSIGNED/")

    # exit code: 0 (could be changed if strict and errors)
    return


if __name__ == "__main__":
    main()
