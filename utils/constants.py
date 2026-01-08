"""Constants for folder to markdown conversion."""

# Enhanced default ignore patterns with better categorization
DEFAULT_IGNORE_PATTERNS = [
    # Node.js
    "node_modules/**",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    ".npmrc",
    "npm-debug.log*",
    
    # Python
    "__pycache__/**",
    "*.py[cod]",
    "*$py.class",
    "*.so",
    ".Python",
    "build/**",
    "develop-eggs/**",
    "dist/**",
    "downloads/**",
    "eggs/**",
    ".eggs/**",
    "lib/**",
    "lib64/**",
    "parts/**",
    "sdist/**",
    "var/**",
    "wheels/**",
    "*.egg-info/**",
    ".installed.cfg",
    "*.egg",
    "MANIFEST",
    ".venv/**",
    "venv/**",
    "env/**",
    ".env",
    ".env.local",
    ".env.*.local",
    
    # Git
    ".git/**",
    ".gitignore",
    ".gitattributes",
    ".gitkeep",
    "LICENSE",
    
    # OS
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    
    # IDE/Editor
    ".vscode/**",
    ".idea/**",
    "*.swp",
    "*.swo",
    "*~",
    
    # Build artifacts
    "build/**",
    "dist/**",
    "target/**",
    "out/**",
    ".next/**",
    ".nuxt/**",
    ".output/**",
    
    # Logs
    "*.log",
    "logs/**",
    
    # Runtime data
    "pids/**",
    "*.pid",
    "*.seed",
    "*.pid.lock",
    
    # Image files
    "*.ico",
    "*.png", 
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.bmp",
    "*.tiff",
    "*.webp",
    "*.svg",
    
    # Other binary files
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    
    # Font files
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
]

# NEW: Explicit directory names to always ignore (case-insensitive)
EXPLICIT_IGNORE_DIRS = {
    # Python
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".coverage",
    
    # Node.js
    "node_modules",
    
    # Git
    ".git",
    
    # Environment
    ".venv", 
    "venv",
    "env",
    ".env",
    
    # Build directories
    "build",
    "dist", 
    "target",
    "out",
    
    # IDE
    ".vscode",
    ".idea",
    
    # OS
    ".DS_Store",
    
    # Cache directories
    ".cache",
    "cache",
    
    # Logs
    "logs",
    
    # Dependencies
    "dependencies",
    "vendor",
    
    # Coverage
    "htmlcov",
    ".coverage",
    
    # Documentation
    "_build",  # Sphinx
}

# Language extensions mapping for better code highlighting
LANGUAGE_EXTENSIONS = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "tsx": "tsx",
    "jsx": "jsx",
    "json": "json",
    "md": "markdown",
    "mdx": "markdown",
    "yml": "yaml",
    "yaml": "yaml",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "html": "html",
    "htm": "html",
    "xml": "xml",
    "csv": "csv",
    "txt": "text",
    "text": "text",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "h": "c",
    "hpp": "cpp",
    "go": "go",
    "rs": "rust",
    "php": "php",
    "rb": "ruby",
    "sql": "sql",
    "dockerfile": "dockerfile",
    "toml": "toml",
    "ini": "ini",
    "cfg": "ini",
}

# Binary file extensions to skip
BINARY_EXTENSIONS = {
    '.ico', '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', 
    '.webp', '.svg', '.pdf', '.zip', '.tar', '.gz', '.7z',
    '.exe', '.dll', '.so', '.dylib', '.woff', '.woff2', '.ttf', '.eot', '.docx', '.xlsx', '.pptx', '.mat',
    '.slx', '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.1', '.fbx', '.unity', '.prefab',
    '.csv', 
}