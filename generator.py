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
import difflib
import traceback

__version__ = "0.3.0"

# Instead of importing all the individual functions and constants
# Just use:
from utils.config import (
    EXT_COMMENT_PLACEHOLDER,
    SPECIAL_FILES,
    get_comment_prefix,
    get_comment_suffix,
    get_default_placeholder,
    load_config_file,
    find_config_candidates,
    merge_placeholders_from_file,
    is_special_file,
    debug_config_loading
)
from utils.load_markdown.load_markdown import load_markdown
from utils.extract_file_structure_block.extract_file_structure_block import extract_file_structure_block
from utils.parse_ascii_tree_block.parse_ascii_tree_block import parse_ascii_tree_block
from utils.map_headings_to_files.map_headings_to_files import map_headings_to_files
from utils.try_rescue_unassigned.try_rescue_unassigned import try_rescue_unassigned
from utils.extract_project_readme.extract_project_readme import extract_project_readme
from utils.reconcile_and_write.reconcile_and_write import reconcile_and_write
from utils.verify_output.verify_output import verify_output
from utils.write_extension_report.write_extension_report import write_extension_report
from utils.resolve_conflict_interactive.resolve_conflict_interactive import resolve_conflict_interactive, resolve_conflict_batch
from utils.write_html_report.write_html_report import write_html_report
from utils.is_probably_file.is_probably_file import is_probably_file
from utils.cache import CacheManager, generate_cache_key, get_cache_info
from utils.set_executable.set_executable import set_executable
from utils.folder_to_markdown.folder_to_markdown import folder_to_markdown
from utils.validate_entry_path.validate_entry_path import validate_entry_path

def main():
    
    start_time = time.time()
    cache_hits = 0
    cache_misses = 0

    parser = argparse.ArgumentParser(
        description="Generate project folder from Markdown spec or convert folder to Markdown",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("input", help="Markdown file path or folder path for --folder-to-md")
    parser.add_argument("-o", "--output", default="output_folder", help="Output folder or markdown file (default: output_folder or folder_name.md)")
    parser.add_argument("--strict", action="store_true", help="Abort on errors or warnings")
    parser.add_argument("--dry", action="store_true", help="Dry run (no writing)")
    parser.add_argument("--preview", action="store_true", help="Preview planned tree and assignments (no writing)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet (errors only)")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    parser.add_argument("--skip-empty", action="store_true", help="Do not create placeholder-only files")
    parser.add_argument("--no-overwrite", action="store_true", help="Do not overwrite existing files")
    parser.add_argument("--json-summary", metavar="FILE", help="Write JSON summary to FILE")
    parser.add_argument("--ignore", nargs="*", default=["__pycache__", "*.pyc", ".git"], help="Glob patterns to ignore")
    parser.add_argument("--files-always", nargs="*", default=["Procfile", "Makefile"], help="Names to always treat as files")
    parser.add_argument("--dirs-always", nargs="*", default=[], help="Names to always treat as dirs")
    parser.add_argument("--placeholders", metavar="FILE", help="JSON file with placeholder overrides")
    parser.add_argument("--config", metavar="FILE", help="Path to generator.config.json to load defaults")
    parser.add_argument("--add-hints", action="store_true", help="Add first-line hint comments to rescued content (disables strip mode)")
    parser.add_argument("--zip", action="store_true", help="Zip the output folder after generation")
    parser.add_argument("--tar", action="store_true", help="Tar.gz the output folder after generation")
    parser.add_argument("--interactive", action="store_true", help="Prompt user when conflicts occur")
    parser.add_argument("--html-report", metavar="FILE", nargs="?", const="report.html", help="Write HTML interactive report (default: report.html)")
    parser.add_argument("--incremental", action="store_true", help="Only regenerate changed files")
    parser.add_argument("--set-exec", action="store_true", help="Set executable flag on *.sh, Procfile, Makefile")
    parser.add_argument("--export-md", metavar="FILE", help="Export generated project back into Markdown")
    parser.add_argument("--extension-report", metavar="FILE", help="Custom report file (default: report.md)")
    parser.add_argument("--folder-to-md", action="store_true", help="Convert folder to markdown file")
    parser.add_argument("--no-compare", action="store_true", help="Disable file structure comparison for --folder-to-md")
    parser.add_argument("--log-file", metavar="FILE", help="Redirect logs to file")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--fallback-level", choices=["low", "medium", "high"], default="low", help="Fallback level for unassigned blocks")
    parser.add_argument("--conflict-strategy", choices=["first", "longest", "shortest", "most_specific", "skip"], default="first", help="Batch conflict resolution strategy")
    parser.add_argument("--cache-debug", action="store_true", help="Debug cache operations")
    parser.add_argument("--cache-size", type=int, default=50, help="Cache size in MB (default: 50)")
    parser.add_argument("--no-mmap", action="store_true", help="Disable memory mapping for cache files")
    parser.add_argument("--fast-json", action="store_true", help="Use ultra-fast JSON parsing (requires ujson)")

    args = parser.parse_args()

    # Validate mutually exclusive flags
    if args.quiet and args.debug:
        logging.error("❌ Cannot use --quiet and --debug together")
        sys.exit(1)
    if args.dry and (args.zip or args.tar or args.set_exec or args.export_md):
        logging.error("❌ --dry cannot be used with --zip, --tar, --set-exec, or --export-md")
        sys.exit(1)
    if args.interactive and args.preview:
        logging.error("❌ --interactive cannot be used with --preview")
        sys.exit(1)

    # Logging setup
    level = logging.DEBUG if args.debug else logging.ERROR if args.quiet else logging.INFO
    handlers = [logging.StreamHandler()]
    if args.log_file:
        try:
            handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
        except Exception as e:
            logging.error(f"❌ Failed to set up log file {args.log_file}: {e}")
            sys.exit(1)
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s", handlers=handlers)

    try:
        # Load config & merge
        cfg = load_config_file(args.config) if args.config else {}
        def merge_flag(name, current, expected_type=None):
            if current not in (None, [], False, "output_folder"):
                return current
            return cfg.get(name, current)

        args.output = merge_flag("output", args.output)
        args.ignore = merge_flag("ignore", args.ignore, list)
        args.files_always = merge_flag("files_always", args.files_always, list)
        args.dirs_always = merge_flag("dirs_always", args.dirs_always, list)
        args.placeholders = merge_flag("placeholders", args.placeholders)
        args.add_hints = merge_flag("add_hints", args.add_hints, bool)
        args.strip_hints = not args.add_hints
        args.zip = merge_flag("zip", args.zip, bool)
        args.tar = merge_flag("tar", args.tar, bool)
        args.no_overwrite = merge_flag("no_overwrite", args.no_overwrite, bool)
        args.conflict_strategy = merge_flag("conflict_strategy", args.conflict_strategy)
        args.cache_size = merge_flag("cache_size", args.cache_size, int)
        args.no_mmap = merge_flag("no_mmap", args.no_mmap, bool)
        args.fast_json = merge_flag("fast_json", args.fast_json, bool)
        
        # Handle folder-to-md mode
        if args.folder_to_md:
            folder = Path(args.input)
            if not folder.exists() or not folder.is_dir():
                logging.error(f"❌ Input must be an existing directory for --folder-to-md: {folder}")
                sys.exit(2)
            output_md = Path(args.output) if args.output.endswith(".md") else Path(f"{folder.name}.md")
            file_list, warnings = folder_to_markdown(
                folder, output_md, compare=not args.no_compare,
                user_ignore=args.ignore, files_always=set(args.files_always), dirs_always=set(args.dirs_always)
            )
            logging.info(f"Generated {output_md} with {len(file_list)} files")
            if warnings:
                logging.warning("Warnings:\n" + "\n".join(warnings))
            if args.json_summary:
                try:
                    with open(args.json_summary, "w", encoding="utf-8") as jf:
                        json.dump({"files_converted": len(file_list), "warnings": warnings}, jf, indent=2)
                except Exception as e:
                    logging.error(f"❌ Failed to write JSON summary: {e}")
                    if args.strict:
                        sys.exit(1)
            if args.strict and warnings:
                sys.exit(1)
            return

        # Placeholders merging
        if args.placeholders:
            try:
                merge_placeholders_from_file(args.placeholders)
            except Exception as e:
                logging.warning(f"⚠️ Failed to merge placeholders: {e}. Using defaults.")

        # Load input markdown
        start = time.time()
        in_path = Path(args.input)
        if not in_path.exists() or not in_path.is_file():
            logging.error(f"❌ Input file not found or not a file: {in_path}")
            sys.exit(2)

        try:
            md_text, tokens = load_markdown(in_path)
        except Exception as e:
            logging.error(f"❌ Failed to parse Markdown: {e}")
            sys.exit(3)

        fs_block = extract_file_structure_block(md_text, tokens)
        if not fs_block:
            logging.error("❌ Could not find a 'File Structure' block in the markdown.")
            if args.fallback_level != "low":
                logging.warning("⚠️ Attempting fallback: Generating empty structure.")
                fs_block = "root/"
            else:
                sys.exit(3)

        files_always = set(args.files_always)
        dirs_always = set(args.dirs_always)

        # Parse and validate tree entries
        tree_entries = parse_ascii_tree_block(fs_block, files_always, dirs_always)
        if not tree_entries:
            logging.warning("⚠️ No valid entries in file structure block.")
            if args.fallback_level == "high":
                logging.info("ℹ️ Fallback: Generating structure from headings.")
                tree_entries = [t["value"].strip().lstrip("./").replace("\\", "/") for t in tokens if t["type"] == "heading"]

        validated_tree_entries = []
        validation_errors = []
        for entry in tree_entries:
            error = validate_entry_path(entry)
            if error:
                validation_errors.append(f"Invalid path entry '{entry}': {error}")
            else:
                validated_tree_entries.append(entry)
        if validation_errors:
            logging.warning("⚠️ Path validation issues:\n" + "\n".join(validation_errors))
            if args.strict:
                sys.exit(1)
        tree_entries = validated_tree_entries
        if not tree_entries:
            logging.error("❌ No valid tree entries after validation")
            sys.exit(3)

        # Map headings to files with conflict resolution
        code_map, unassigned, mapping_warnings, heading_map = map_headings_to_files(
            tokens, tree_entries, files_always, dirs_always, strip_hints=args.strip_hints, interactive=args.interactive
        )

        # Handle conflicts in code_map
        if code_map:
            for target, blocks in list(code_map.items()):
                if len(blocks) > 1:  # Multiple blocks for one file
                    if args.interactive:
                        try:
                            resolved_blocks = resolve_conflict_interactive(target, blocks)
                            if resolved_blocks:
                                code_map[target] = [resolved_blocks] if isinstance(resolved_blocks, str) else resolved_blocks
                                mapping_warnings.append(f"ℹ️ Interactively resolved conflict for {target}: kept {len(code_map[target])} block(s)")
                            else:
                                unassigned.extend(blocks)
                                del code_map[target]
                                mapping_warnings.append(f"ℹ️ Skipped conflict for {target} during interactive resolution")
                        except Exception as e:
                            logging.warning(f"⚠️ Failed interactive resolution for {target}: {e}")
                            mapping_warnings.append(f"⚠️ Conflict unresolved for {target}")
                    else:
                        try:
                            resolved = resolve_conflict_batch(target, blocks, strategy=args.conflict_strategy)
                            if resolved:
                                code_map[target] = [resolved] if isinstance(resolved, str) else resolved
                                mapping_warnings.append(f"ℹ️ Batch resolved conflict for {target} using {args.conflict_strategy}")
                            else:
                                unassigned.extend(blocks)
                                del code_map[target]
                                mapping_warnings.append(f"ℹ️ Skipped conflict for {target} using {args.conflict_strategy}")
                        except Exception as e:
                            logging.warning(f"⚠️ Failed batch resolution for {target}: {e}")
                            mapping_warnings.append(f"⚠️ Conflict unresolved for {target}")

        unassigned, rescue_warnings = try_rescue_unassigned(
            unassigned, tree_entries, code_map, heading_map, strip_hints=args.strip_hints, interactive=args.interactive, fallback_level=args.fallback_level
        )

        # Fuzzy matching for unassigned blocks
        if unassigned and args.fallback_level in ("medium", "high"):
            still_unassigned = []
            for code in unassigned:
                lines = code.splitlines()
                hint = lines[0].strip().lstrip("./").replace("\\", "/") if lines else ""
                if hint:
                    closest = difflib.get_close_matches(hint, tree_entries, n=3, cutoff=0.8)
                    if closest:
                        if args.interactive:
                            try:
                                target = resolve_conflict_interactive(hint, closest)
                                if target:
                                    code_map.setdefault(target, []).append(code)
                                    rescue_warnings.append(f"ℹ️ Interactively assigned block to {target}")
                                    continue
                            except Exception as e:
                                logging.warning(f"⚠️ Failed interactive assignment for hint '{hint}': {e}")
                        else:
                            target = resolve_conflict_batch(hint, closest, strategy=args.conflict_strategy)
                            if target:
                                code_map.setdefault(target, []).append(code)
                                rescue_warnings.append(f"ℹ️ Batch assigned block to {target} using {args.conflict_strategy}")
                                continue
                still_unassigned.append(code)
            unassigned = still_unassigned

        all_warnings = mapping_warnings + rescue_warnings
        errors = []

        # Preview mode
        if args.preview:
            print("\n---- Preview: Planned file assignments ----\n")
            for f in sorted(tree_entries):
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
                try:
                    with open(args.json_summary, "w", encoding="utf-8") as jf:
                        json.dump({
                            "files_in_tree": len([f for f in tree_entries if is_probably_file(Path(f).name, files_always, dirs_always)]),
                            "unassigned_blocks": len(unassigned)
                        }, jf, indent=2)
                except Exception as e:
                    logging.error(f"❌ Failed to write JSON summary: {e}")
                    if args.strict:
                        sys.exit(1)
            return

        # Prepare output
        out_root = Path(args.output)
        if out_root.exists() and not args.dry and not args.no_overwrite:
            try:
                shutil.rmtree(out_root)
            except Exception as e:
                logging.error(f"❌ Failed to remove existing output directory {out_root}: {e}")
                sys.exit(1)

        # Enhanced incremental mode with performance cache
        # Enhanced incremental mode with performance cache
        cache_manager = None
        file_cache = {}

        if args.incremental:
            try:
                cache_manager = CacheManager(
                    cache_dir=out_root / ".generator_cache",
                    max_size_mb=args.cache_size,
                    use_mmap=not args.no_mmap,
                    auto_create_dirs=True
                )
                
                # Load file modification cache
                file_cache = cache_manager.load("file_modifications") or {}
                
                if args.verbose:
                    cache_info = cache_manager.get_info("file_modifications")
                    logging.info(f"ℹ️ Cache loaded: {cache_info.get('entry_count', 0)} entries, {cache_info.get('size_bytes', 0)} bytes")
                    
            except Exception as e:
                logging.warning(f"⚠️ Failed to initialize cache: {e}. Continuing without cache.")
                file_cache = {}
        else:
            file_cache = {}
        created_dirs, created_files, write_warnings, total_lines_written, placeholders_created, files_written_count = reconcile_and_write(
            tree_entries, code_map, out_root,
            dry_run=args.dry, verbose=args.verbose, skip_empty=args.skip_empty,
            ignore_patterns=args.ignore, files_always=files_always, dirs_always=dirs_always,
            no_overwrite=args.no_overwrite, heading_map=heading_map, cache=file_cache,
            cache_manager=cache_manager  # Pass the cache manager for advanced operations
        )

        if unassigned and not args.dry:
            un_dir = out_root / "UNASSIGNED"
            try:
                un_dir.mkdir(parents=True, exist_ok=True)
                for i, block in enumerate(unassigned, 1):
                    (un_dir / f"unassigned_{i}.txt").write_text(block, encoding="utf-8")
            except Exception as e:
                logging.warning(f"⚠️ Failed to save unassigned blocks: {e}")

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
            try:
                with open(args.json_summary, "w", encoding="utf-8") as jf:
                    json.dump(summary, jf, indent=2)
            except Exception as e:
                logging.error(f"❌ Failed to write JSON summary: {e}")
                if args.strict:
                    sys.exit(1)

        report_path = Path(args.extension_report) if args.extension_report else (out_root / "report.md")
        write_extension_report(out_root, tree_entries, code_map, unassigned,
                              write_warnings + all_warnings, errors, report_path,
                              summary, elapsed, rescue_warnings)

        if args.html_report:
            html_path = Path(args.html_report) if args.html_report != "report.html" else (out_root / "report.html")
            try:
                write_html_report(
                    tree_entries, out_root, summary, html_path,
                    code_map=code_map, files_always=files_always,
                    dirs_always=dirs_always, excluded_files=set(args.ignore)
                )
                logging.info(f"Generated HTML report at {html_path}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to write HTML report: {e}")

        project_readme = extract_project_readme(tokens, tree_entries)
        if project_readme and not args.dry:
            project_readme_path = out_root / "README.md"
            try:
                mode = "a" if project_readme_path.exists() else "w"
                with open(project_readme_path, mode, encoding="utf-8") as f:
                    if mode == "a":
                        f.write("\n\n")
                    f.write(project_readme)
            except Exception as e:
                logging.warning(f"⚠️ Failed to write README: {e}")

        # Archives
        if args.zip and not args.dry:
            try:
                shutil.make_archive(str(out_root), "zip", root_dir=out_root)
                logging.info(f"Created zip archive: {out_root}.zip")
            except Exception as e:
                logging.warning(f"⚠️ Failed to create zip archive: {e}")

        if args.tar and not args.dry:
            try:
                with tarfile.open(str(out_root) + ".tar.gz", "w:gz") as tar:
                    tar.add(out_root, arcname=out_root.name)
                logging.info(f"Created tar.gz archive: {out_root}.tar.gz")
            except Exception as e:
                logging.warning(f"⚠️ Failed to create tar.gz archive: {e}")

        if args.incremental and cache_manager:
            try:
                # Update cache with current file modifications
                cache_data = {}
                for file_path in created_files:
                    full_path = out_root / file_path
                    if full_path.exists():
                        cache_data[file_path] = {
                            'modified': full_path.stat().st_mtime,
                            'size': full_path.stat().st_size,
                            'hash': generate_cache_key(full_path.read_text(encoding='utf-8'))
                        }
                
                # Save updated cache
                cache_manager.save("file_modifications", cache_data)
                
                # Log cache statistics
                cache_stats = cache_manager.get_stats()
                logging.debug(f"ℹ️ Cache stats: {cache_stats}")
                
            except Exception as e:
                logging.warning(f"⚠️ Failed to update cache: {e}")

        if args.set_exec:
            for f in created_files:
                if f.endswith(".sh") or Path(f).name in ("Procfile", "Makefile"):
                    try:
                        set_executable(Path(f))
                    except Exception as e:
                        logging.warning(f"⚠️ Failed to set executable flag on {f}: {e}")

        if args.export_md:
            export_path = Path(args.output) / Path(args.export_md).name
            try:
                folder_to_markdown(out_root, export_path, user_ignore=args.ignore, files_always=files_always, dirs_always=dirs_always)
                logging.info(f"Exported Markdown to {export_path}")
            except Exception as e:
                logging.warning(f"⚠️ Failed to export Markdown: {e}")

        # Enforce strict mode
        if args.strict and (summary["unassigned_blocks"] > 0 or len(summary["issues"]) > 0 or len(errors) > 0):
            logging.error("❌ Strict mode: Exiting due to issues or unassigned blocks")
            sys.exit(1)

        # Cache debugging
        if args.cache_debug and cache_manager:
            try:
                cache_info = cache_manager.debug("file_modifications")
                logging.info(f"🔍 Cache debug info: {cache_info}")
                
                # Also debug the main cache file
                cache_file_info = get_cache_info(out_root / ".generator_cache" / "file_modifications.json")
                logging.info(f"🔍 Cache file info: {cache_file_info}")
            except Exception as e:
                logging.warning(f"⚠️ Cache debugging failed: {e}")
        
            # Cache performance statistics
            if args.incremental and cache_manager:
                from utils.reconcile_and_write.reconcile_and_write import get_cache_performance_stats
                cache_stats = get_cache_performance_stats(cache_manager)
                if cache_stats:
                    logging.info(f"ℹ️ Cache performance: {cache_stats['cache_hits']} hits, {cache_stats['cache_misses']} misses ({cache_stats['cache_hit_ratio']:.1%} hit ratio)")

        # Final console summary
        if level <= logging.INFO:
            logging.info("\n---- Final Report ----")
            for k, v in sorted(summary.items()):
                logging.info(f"{k}: {v}")
            
            # Add cache statistics if available
            if args.incremental and cache_manager:
                cache_stats = cache_manager.get_stats()
                logging.info(f"cache_hits: {cache_stats.get('hits', 0)}")
                logging.info(f"cache_misses: {cache_stats.get('misses', 0)}")
                if cache_stats.get('hits', 0) + cache_stats.get('misses', 0) > 0:
                    hit_ratio = cache_stats['hits'] / (cache_stats['hits'] + cache_stats['misses'])
                    logging.info(f"cache_hit_ratio: {hit_ratio:.1%}")
            
            if summary["unassigned_blocks"]:
                logging.warning(f"⚠️ {summary['unassigned_blocks']} unassigned block(s) saved in UNASSIGNED/")
            elif not summary["issues"]:
                logging.info("✅ All files created and verified successfully")
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()