from typing import Set
from utils.constants import DEFAULT_IGNORE_PATTERNS
# File detection + special cases with better categorization
SPECIAL_FILES: Set[str] = {
    # Build and dependency files
    "dockerfile", "makefile", "procfile",
    "package.json", "requirements.txt", "pipfile", "gemfile",
    "cargo.toml", "go.mod", "composer.json", "pom.xml",
    
    # Configuration files
    ".gitignore", ".eslintrc", ".editorconfig", ".prettierrc",
    ".env", ".env.example", ".env.local", ".env.production",
    "tsconfig.json", "webpack.config.js", "rollup.config.js",
    "vite.config.js", "jest.config.js", "babel.config.js",
    
    # Documentation
    "readme", "readme.md", "readme.txt", "contributing", "authors",
    "changelog", "changelog.md", "license", "license.md", "code_of_conduct",
    
    # Project-specific
    "firestore.rules", "docker-compose.yml", "docker-compose.yaml",
    ".travis.yml", "github/workflows", "gitlab-ci.yml",
    
    # Runtime and deployment
    "procfile", "manifest.yml", "app.yaml", "cloudbuild.yaml",
}

def is_special_file(filename: str) -> bool:
    """
    Check if filename matches known special file patterns.
    
    Args:
        filename: Filename to check
        
    Returns:
        True if filename matches special file patterns
    """
    if not filename:
        return False
    
    name_lower = filename.lower().strip()
    if name_lower in DEFAULT_IGNORE_PATTERNS:
        return False
    
    # Exact matches
    if name_lower in SPECIAL_FILES:
        return True
    
    # Pattern matches
    if name_lower.startswith(".env") or name_lower.endswith(".config.js"):
        return True
    
    # Directory patterns
    if "/" in name_lower and any(special in name_lower for special in ["github/workflows", ".github/"]):
        return True
    
    return False