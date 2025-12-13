from pathlib import Path
from typing import List, Dict, Optional, Set
import json
import logging

from utils.is_probably_file.is_probably_file import is_probably_file
from utils.normalize_path_segment.normalize_path_segment import normalize_path_segment

def write_html_report(
    tree_entries: List[str],
    out_root: Path,
    summary: Dict,
    html_path: Path,
    code_map: Optional[Dict[str, List[str]]] = None,
    files_always: Optional[Set[str]] = None,
    dirs_always: Optional[Set[str]] = None,
    excluded_files: Optional[Set[str]] = None
) -> bool:
    """
    Generate an HTML report of the generation results with comprehensive status tracking.
    
    Args:
        tree_entries: List of all tree entries (files and directories)
        out_root: Root directory of generated output
        summary: Summary statistics dictionary
        html_path: Path to write HTML report
        code_map: Mapping of files to code blocks (optional)
        files_always: Set of names to always treat as files
        dirs_always: Set of names to always treat as directories
        excluded_files: Set of files to exclude from report
        
    Returns:
        True if report was generated successfully
    """
    # Input validation
    if not isinstance(out_root, Path):
        logging.error("❌ Output root must be a Path object")
        return False
    
    if not isinstance(html_path, Path):
        logging.error("❌ HTML path must be a Path object")
        return False
    
    if not tree_entries:
        logging.warning("⚠️ No tree entries provided for HTML report")
    
    files_always = files_always or set()
    dirs_always = dirs_always or set()
    excluded_files = excluded_files or set()
    
    try:
        # Clean and process tree entries
        cleaned_entries = clean_tree_entries_for_report(tree_entries)
        
        html_content = generate_html_content(
            cleaned_entries, out_root, summary, code_map, 
            files_always, dirs_always, excluded_files
        )
        
        # Write HTML file
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_content, encoding="utf-8")
        logging.info(f"✅ HTML report generated: {html_path}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed to generate HTML report: {e}")
        return False

def clean_tree_entries_for_report(tree_entries: List[str]) -> List[tuple[str, str]]:
    """
    Clean ASCII tree characters for HTML report display.
    Returns list of (original_entry, display_entry)
    """
    cleaned_entries = []
    path_stack = []
    
    for entry in tree_entries:
        # Calculate indent level
        indent_chars = 0
        for char in ['│', '├', '└']:
            indent_chars += entry.count(char)
        
        # Clean the line
        clean_line = entry
        for char in ['│', '├', '└', '──', '─']:
            clean_line = clean_line.replace(char, ' ')
        
        clean_line = ' '.join(clean_line.split()).strip()
        
        if not clean_line:
            continue
            
        is_directory = clean_line.endswith('/')
        name = clean_line.rstrip('/')
        
        # Update path stack
        indent_level = max(0, indent_chars - 1)
        path_stack = path_stack[:indent_level]
        
        if is_directory:
            path_stack.append(name)
            display_path = '/'.join(path_stack)
        else:
            if path_stack:
                display_path = '/'.join(path_stack + [name])
            else:
                display_path = name
        
        cleaned_entries.append((entry, display_path))
    
    return cleaned_entries

def generate_html_content(
    cleaned_entries: List[tuple[str, str]],
    out_root: Path,
    summary: Dict,
    code_map: Optional[Dict[str, List[str]]],
    files_always: Set[str],
    dirs_always: Set[str],
    excluded_files: Set[str]
) -> str:
    """
    Generate the complete HTML content.
    """
    html_lines = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "<title>Project Generation Report</title>",
        "<style>",
        "* { box-sizing: border-box; }",
        "body { font-family: 'Monaco', 'Consolas', 'Courier New', monospace; margin: 0; padding: 20px; background: #f5f5f5; }",
        ".container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }",
        "h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }",
        "h2 { color: #555; margin-top: 30px; }",
        ".file-list { list-style: none; padding: 0; margin: 20px 0; }",
        ".file-item { padding: 8px 12px; margin: 2px 0; border-radius: 4px; display: flex; align-items: center; }",
        ".file-item:hover { background: #f8f9fa; }",
        ".file-name { flex: 1; }",
        ".file-status { margin-left: 10px; font-weight: bold; }",
        ".ok { color: #28a745; background: #f8fff9; }",
        ".warn { color: #ffc107; background: #fffef0; }",
        ".err { color: #dc3545; background: #fff5f5; }",
        ".info { color: #17a2b8; background: #f0f9ff; }",
        ".summary { background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; }",
        ".stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }",
        ".stat-card { background: white; padding: 15px; border-radius: 6px; border-left: 4px solid #007bff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        ".stat-value { font-size: 24px; font-weight: bold; color: #333; }",
        ".stat-label { color: #666; font-size: 14px; }",
        "pre { background: #f8f9fa; padding: 15px; border-radius: 6px; overflow-x: auto; }",
        ".timestamp { color: #666; font-size: 14px; margin-bottom: 20px; }",
        "</style>",
        "</head>",
        "<body>",
        "<div class='container'>",
        "<h1>🚀 Project Generation Report</h1>",
        f"<div class='timestamp'>Generated at: {generate_timestamp()}</div>"
    ]
    
    # Add summary statistics
    html_lines.extend(generate_summary_section(summary))
    
    # Add file tree
    html_lines.extend(generate_file_tree_section(
        cleaned_entries, out_root, code_map, files_always, dirs_always, excluded_files
    ))
    
    # Add detailed summary
    html_lines.extend([
        "<h2>📋 Detailed Summary</h2>",
        "<div class='summary'>",
        "<pre>" + json.dumps(summary, indent=2, ensure_ascii=False) + "</pre>",
        "</div>"
    ])
    
    html_lines.extend([
        "</div>",
        "</body>",
        "</html>"
    ])
    
    return "\n".join(html_lines)

def generate_summary_section(summary: Dict) -> List[str]:
    """Generate the summary statistics section."""
    lines = [
        "<h2>📊 Quick Stats</h2>",
        "<div class='stats-grid'>"
    ]
    
    stats_to_show = [
        ("total_files_expected", "📄 Expected Files", "#007bff"),
        ("files_found", "✅ Files Created", "#28a745"),
        ("files_missing", "❌ Missing Files", "#dc3545"),
        ("files_empty", "⚠️ Empty Files", "#ffc107"),
        ("directories_expected", "📁 Expected Dirs", "#17a2b8"),
        ("directories_found", "📁 Directories", "#6f42c1"),
    ]
    
    for key, label, color in stats_to_show:
        value = summary.get(key, 0)
        lines.append(f"""
            <div class='stat-card' style='border-left-color: {color}'>
                <div class='stat-value'>{value}</div>
                <div class='stat-label'>{label}</div>
            </div>
        """)
    
    lines.append("</div>")
    return lines

def generate_file_tree_section(
    cleaned_entries: List[tuple[str, str]],
    out_root: Path,
    code_map: Optional[Dict[str, List[str]]],
    files_always: Set[str],
    dirs_always: Set[str],
    excluded_files: Set[str]
) -> List[str]:
    """Generate the file tree section with status indicators."""
    lines = [
        "<h2>📁 Generated Structure</h2>",
        "<ul class='file-list'>"
    ]
    
    excluded_count = 0
    
    for original_entry, display_path in cleaned_entries:
        # Check if excluded
        if display_path in excluded_files:
            excluded_count += 1
            continue
            
        # Determine if it's a file or directory
        name = Path(display_path).name
        is_file = is_probably_file(name, files_always, dirs_always)
        
        if not is_file:
            # Directory
            lines.append(f"<li class='file-item info'><span class='file-name'>{display_path}/</span></li>")
        else:
            # File - check status
            status_html = get_file_status_html(display_path, out_root, code_map)
            lines.append(f"<li class='file-item {status_html['class']}'>"
                        f"<span class='file-name'>{display_path}</span>"
                        f"<span class='file-status'>{status_html['icon']} {status_html['text']}</span>"
                        f"</li>")
    
    lines.append("</ul>")
    
    if excluded_count > 0:
        lines.append(f"<p><em>Note: {excluded_count} files excluded from report</em></p>")
    
    return lines

def get_file_status_html(
    file_path: str,
    out_root: Path,
    code_map: Optional[Dict[str, List[str]]]
) -> Dict[str, str]:
    """Get HTML status information for a file."""
    path = out_root / file_path
    
    if not path.exists():
        return {"class": "err", "icon": "❌", "text": "MISSING"}
    
    if not path.is_file():
        return {"class": "err", "icon": "❌", "text": "NOT A FILE"}
    
    try:
        # Check file content
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        
        if not content:
            return {"class": "warn", "icon": "⚠️", "text": "EMPTY"}
        
        # Check if it's a placeholder
        if is_placeholder_content(content):
            return {"class": "warn", "icon": "⏳", "text": "PLACEHOLDER"}
        
        # Check code blocks if code_map provided
        if code_map and file_path in code_map:
            assigned_blocks = code_map[file_path]
            if len(assigned_blocks) > 1:
                return {"class": "info", "icon": "🔀", "text": f"{len(assigned_blocks)} BLOCKS"}
        
        return {"class": "ok", "icon": "✅", "text": "GENERATED"}
        
    except Exception as e:
        return {"class": "err", "icon": "❌", "text": f"ERROR: {str(e)[:30]}..."}

def is_placeholder_content(content: str) -> bool:
    """Check if content appears to be a placeholder."""
    placeholder_indicators = [
        "# TODO", "// TODO", "<!-- TODO", "TODO:", "FIXME",
        "# PLACEHOLDER", "// PLACEHOLDER", "<!-- PLACEHOLDER",
        "{{", "}}", "<<", ">>"  # Template markers
    ]
    
    first_lines = '\n'.join(content.splitlines()[:3]).lower()
    return any(indicator.lower() in first_lines for indicator in placeholder_indicators)

def generate_timestamp() -> str:
    """Generate a formatted timestamp."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Simple version for backward compatibility
def write_html_report_simple(
    tree_entries: List[str],
    out_root: Path,
    summary: Dict,
    html_path: Path
) -> bool:
    """Simple version maintaining original interface."""
    return write_html_report(tree_entries, out_root, summary, html_path)