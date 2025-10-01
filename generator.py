#!/usr/bin/env python3
"""
generator.py
Markdown → Project folder generator (Phase 1) and Folder → Markdown converter

Orchestrates function calls to generate project structure from Markdown or convert a folder to Markdown.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
import shutil
import tarfile
import json
from pathlib import Path

from utils.config.config import load_config_file, merge_placeholders_from_file
from utils.load_markdown.load_markdown import load_markdown
from utils.extract_file_structure_block.extract_file_structure_block import extract_file_structure_block
from utils.parse_ascii_tree_block.parse_ascii_tree_block import parse_ascii_tree_block
from utils.map_headings_to_files.map_headings_to_files import map_headings_to_files
from utils.try_rescue_unassigned.try_rescue_unassigned import try_rescue_unassigned
from utils.extract_project_readme.extract_project_readme import extract_project_readme
from utils.reconcile_and_write.reconcile_and_write import reconcile_and_write
from utils.verify_output.verify_output import verify_output
from utils.write_extension_report.write_extension_report import write_extension_report
from utils.resolve_conflict_interactive.resolve_conflict_interactive import resolve_conflict_interactive
from utils.write_html_report.write_html_report import write_html_report
from utils.is_probably_file.is_probably_file import is_probably_file
from utils.should_update.should_update import should_update
from utils.load_cache.load_cache import load_cache
from utils.save_cache.save_cache import save_cache
from utils.set_executable.set_executable import set_executable
from utils.export_to_markdown.export_to_markdown import export_to_markdown, folder_to_markdown

def main():
    parser = argparse.ArgumentParser(description="Generate project folder from Markdown spec or convert folder to Markdown")
    parser.add_argument("input", help="Markdown file path or folder path for --folder-to-md")
    parser.add_argument("-o", "--output", default="output_folder", help="Output folder or markdown file (default: output_folder or folder_name.md)")
    parser.add_argument("--strict", action="store_true", help="Abort on errors")
    parser.add_argument("--dry", action="store_true", help="Dry run (no writing)")
    parser.add_argument("--preview", action="store_true", help="Preview planned tree and assignments (no writing)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet (errors only)")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    parser.add_argument("--skip-empty", action="store_true", help="Do not create placeholder-only files")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing files")
    parser.add_argument("--json-summary", metavar="FILE", help="Write JSON summary to FILE")
    parser.add_argument("--ignore", nargs="*", default=[], help="Glob patterns to ignore (e.g. '*.md')")
    parser.add_argument("--files-always", nargs="*", default=[], help="Names to always treat as files")
    parser.add_argument("--dirs-always", nargs="*", default=[], help="Names to always treat as dirs")
    parser.add_argument("--placeholders", metavar="FILE", help="JSON file with placeholder overrides")
    parser.add_argument("--config", metavar="FILE", help="Path to generator.config.json to load defaults")
    parser.add_argument("--strip-hints", action="store_true", help="Strip first-line hint comments from rescued content")
    parser.add_argument("--zip", action="store_true", help="Zip the output folder after generation")
    parser.add_argument("--tar", action="store_true", help="Tar.gz the output folder after generation")
    parser.add_argument("--interactive", action="store_true", help="Prompt user when conflicts occur")
    parser.add_argument("--html-report", metavar="FILE", nargs="?", const="report.html", default=None, help="Write HTML interactive report (default: report.html)")
    parser.add_argument("--incremental", action="store_true", help="Only regenerate changed files")
    parser.add_argument("--set-exec", action="store_true", help="Set executable flag on *.sh and Procfile/Makefile")
    parser.add_argument("--export-md", metavar="FILE", help="Export generated project back into Markdown")
    parser.add_argument("--extension-report", metavar="FILE", help="Custom report file (default: report.md)")
    parser.add_argument("--folder-to-md", action="store_true", help="Convert folder to markdown file")
    parser.add_argument("--no-compare", action="store_true", help="Disable file structure comparison for --folder-to-md")

    args = parser.parse_args()

    # Load config & merge
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

    # Logging setup
    if args.debug:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    # Handle folder-to-md mode
    if args.folder_to_md:
        folder = Path(args.input)
        if not folder.is_dir():
            logging.error(f"❌ Input must be a directory for --folder-to-md: {folder}")
            sys.exit(2)
        output_md = Path(args.output) if args.output.endswith(".md") else Path(f"{folder.name}.md")
        file_list, warnings = folder_to_markdown(folder, output_md, compare=not args.no_compare)
        logging.info(f"Generated {output_md} with {len(file_list)} files")
        if warnings:
            logging.warning("Warnings:\n" + "\n".join(warnings))
        if args.json_summary:
            with open(args.json_summary, "w", encoding="utf-8") as jf:
                json.dump({"files_converted": len(file_list), "warnings": warnings}, jf, indent=2)
        return

    # Placeholders merging
    merge_placeholders_from_file(args.placeholders)

    # Load input markdown
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

    # Preview mode
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

    # Prepare output
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

    # Reports
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

    # Archives
    if args.zip and not args.dry:
        shutil.make_archive(str(out_root), "zip", root_dir=out_root)
    if args.tar and not args.dry:
        with tarfile.open(str(out_root) + ".tar.gz", "w:gz") as tar:
            tar.add(out_root, arcname=out_root.name)

    # Phase 2 features
    if args.interactive:
        logging.info("ℹ️ Interactive conflict resolution enabled")
        resolve_conflict_interactive(created_files, out_root)

    if args.html_report:
        args.html_report = Path(args.output) / Path(args.html_report).name
        write_html_report(tree_entries, out_root, summary, Path(args.html_report))

    if args.incremental:
        cache_file = out_root / ".generator_cache.json"
        cache = load_cache(cache_file)
        save_cache(cache_file, cache)

    if args.set_exec:
        for f in created_files:
            if f.endswith(".sh") or Path(f).name in ("Procfile", "Makefile"):
                set_executable(Path(f))

    if args.export_md:
        args.export_md = Path(args.output) / Path(args.export_md).name
        export_to_markdown(out_root, Path(args.export_md))

    # Final console summary
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