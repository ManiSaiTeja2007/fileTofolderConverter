from pathlib import Path
import json
import logging

# Default placeholders by extension
EXT_COMMENT_PLACEHOLDER: dict[str, str] = {
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

# File detection + special cases
SPECIAL_FILES = {
    "docker",
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

def load_config_file(explicit_path: str | None = None) -> dict:
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
    script_dir = Path(__file__).parent.parent.parent if "__file__" in globals() else Path.cwd()
    candidates.append(script_dir / "generator.config.json")

    for p in candidates:
        try:
            if p and p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            continue
    return {}

def merge_placeholders_from_file(placeholders_path: str | None):
    """If provided, merge external JSON placeholders into EXT_COMMENT_PLACEHOLDER."""
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