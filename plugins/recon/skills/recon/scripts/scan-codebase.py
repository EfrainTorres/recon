#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["tiktoken"]
# ///
"""
Codebase Scanner for Recon
Scans a directory tree, respects .gitignore, and outputs comprehensive codebase metadata.

Features:
- Token counting with tiktoken
- Full .gitignore support (negation, nested files)
- Git intelligence (churn, staleness, co-change coupling)
- Entrypoint detection (package.json, pyproject.toml, Cargo.toml, etc.)
- Config surface listing
- Exact duplicate detection (content hashing)
- Generated code detection
- TODO/FIXME counting

Run with: uv run scan-codebase.py [path]
UV will automatically install tiktoken in an isolated environment.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

try:
    import tiktoken
except ImportError:
    print("ERROR: tiktoken not installed.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Recommended: Install UV for automatic dependency handling:", file=sys.stderr)
    print("  curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
    print("  Then run: uv run scan-codebase.py", file=sys.stderr)
    print("", file=sys.stderr)
    print("Or install tiktoken manually: pip install tiktoken", file=sys.stderr)
    sys.exit(1)

SCANNER_VERSION = "2.0.0"

# Default patterns to always ignore (common non-code files)
DEFAULT_IGNORE = {
    # Directories
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".output",
    "coverage",
    ".coverage",
    ".nyc_output",
    "target",  # Rust/Java
    "vendor",  # Go/PHP
    ".bundle",
    ".cargo",
    # Files
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.o",
    "*.a",
    "*.lib",
    "*.class",
    "*.jar",
    "*.war",
    "*.egg",
    "*.whl",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
    # Binary/media
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.webp",
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.avi",
    "*.mov",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.rar",
    "*.7z",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.otf",
    # Large generated files
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.chunk.js",
    "*.bundle.js",
}

# Text file extensions
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".xml",
    ".md", ".mdx", ".txt", ".rst",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".sql", ".graphql", ".gql", ".proto",
    ".go", ".rs", ".rb", ".php", ".java", ".kt", ".kts", ".scala",
    ".clj", ".cljs", ".edn", ".ex", ".exs", ".erl", ".hrl",
    ".hs", ".lhs", ".ml", ".mli", ".fs", ".fsx", ".fsi",
    ".cs", ".vb", ".swift", ".m", ".mm", ".h", ".hpp",
    ".c", ".cpp", ".cc", ".cxx", ".r", ".R", ".jl", ".lua",
    ".vim", ".el", ".lisp", ".scm", ".rkt", ".zig", ".nim",
    ".d", ".dart", ".v", ".sv", ".vhd", ".vhdl",
    ".tf", ".hcl", ".dockerfile", ".containerfile",
    ".makefile", ".cmake", ".gradle", ".groovy", ".rake",
    ".gemspec", ".podspec", ".cabal", ".nix", ".dhall",
    ".jsonc", ".json5", ".cson", ".ini", ".cfg", ".conf", ".config",
    ".env", ".env.example", ".env.local", ".env.development", ".env.production",
    ".gitignore", ".gitattributes", ".editorconfig",
    ".prettierrc", ".eslintrc", ".stylelintrc", ".babelrc",
    ".nvmrc", ".ruby-version", ".python-version", ".node-version", ".tool-versions",
}

# Extensionless text files
TEXT_NAMES = {
    "readme", "license", "licence", "changelog", "authors", "contributors",
    "copying", "dockerfile", "containerfile", "makefile", "rakefile",
    "gemfile", "procfile", "brewfile", "vagrantfile", "justfile", "taskfile",
}

# Config file patterns by category
CONFIG_PATTERNS = {
    "package": [
        "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "go.sum",
        "Gemfile", "composer.json", "pom.xml", "build.gradle", "build.gradle.kts",
        "requirements.txt", "setup.py", "setup.cfg", "pnpm-workspace.yaml",
    ],
    "typescript": ["tsconfig.json", "tsconfig.*.json", "jsconfig.json"],
    "build": [
        "webpack.config.*", "vite.config.*", "rollup.config.*", "esbuild.config.*",
        "babel.config.*", ".babelrc*", "metro.config.*", "next.config.*",
        "nuxt.config.*", "svelte.config.*", "astro.config.*",
    ],
    "ci": [
        ".github/workflows/*.yml", ".github/workflows/*.yaml",
        ".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml",
        ".travis.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml",
    ],
    "docker": [
        "Dockerfile", "Dockerfile.*", "docker-compose.yml", "docker-compose.*.yml",
        "compose.yml", "compose.*.yml", ".dockerignore",
    ],
    "infrastructure": [
        "*.tf", "*.tfvars", "terraform.tfstate", "kubernetes/*.yaml",
        "k8s/*.yaml", "helm/**/*.yaml", "Chart.yaml", "values.yaml",
    ],
    "env": [".env.example", ".env.sample", ".env.template", ".env.local.example"],
    "linting": [
        ".eslintrc*", ".prettierrc*", ".stylelintrc*", ".editorconfig",
        "biome.json", ".biomeignore", "deno.json", "deno.jsonc",
        ".pylintrc", "pyproject.toml", "setup.cfg", ".flake8", ".ruff.toml", "ruff.toml",
    ],
}

# Generated code indicators (directory names)
GENERATED_PATH_NAMES = {
    "generated", "dist", "build", ".next", ".nuxt", "coverage",
    "__generated__", "node_modules", "vendor", ".cache", "out",
    "__pycache__", ".tox", ".eggs",
}

# Generated code path patterns (for fnmatch)
GENERATED_PATH_PATTERNS = [
    "*.egg-info",
]

GENERATED_MARKERS = [
    "generated", "do not edit", "auto-generated", "this file is generated",
    "@generated", "automatically generated", "autogenerated",
]

@dataclass
class GitIgnoreRule:
    """Represents a single .gitignore rule."""
    pattern: str
    negation: bool
    directory_only: bool
    anchored: bool  # Pattern starts from root
    source_dir: Path  # Directory containing the .gitignore


@dataclass
class FileInfo:
    """Information about a single file."""
    path: str
    tokens: int
    size_bytes: int
    content_hash: Optional[str] = None
    is_generated: bool = False
    todo_count: int = 0
    fixme_count: int = 0
    # Git info (populated separately)
    git_commits_90d: int = 0
    git_last_commit: Optional[str] = None


@dataclass
class Entrypoint:
    """Detected entrypoint."""
    path: str
    type: str  # e.g., "package.json main", "convention"
    evidence: str


@dataclass
class ScanResult:
    """Complete scan results."""
    root: str
    scanner_version: str
    timestamp: str
    args: dict
    files: list
    directories: list
    total_tokens: int
    total_files: int
    skipped: list
    entrypoints: list
    config_surface: dict
    duplicates: dict  # hash -> [paths]
    git_available: bool
    git_stats: dict  # churn, staleness, etc.
    generated_files: list
    todo_summary: dict


def parse_gitignore_file(gitignore_path: Path, source_dir: Path) -> list[GitIgnoreRule]:
    """Parse a .gitignore file and return rules."""
    rules = []
    if not gitignore_path.exists():
        return rules

    try:
        with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n\r")
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Handle negation
                negation = line.startswith("!")
                if negation:
                    line = line[1:]

                # Handle directory-only patterns
                directory_only = line.endswith("/")
                if directory_only:
                    line = line[:-1]

                # Handle anchored patterns (starting with /)
                anchored = line.startswith("/")
                if anchored:
                    line = line[1:]

                # Also anchor patterns with / in the middle
                if "/" in line and not anchored:
                    anchored = True

                rules.append(GitIgnoreRule(
                    pattern=line,
                    negation=negation,
                    directory_only=directory_only,
                    anchored=anchored,
                    source_dir=source_dir,
                ))
    except Exception:
        pass

    return rules


def collect_gitignore_rules(root: Path) -> list[GitIgnoreRule]:
    """Collect all .gitignore rules from root and nested directories."""
    all_rules = []

    # Parse root .gitignore
    all_rules.extend(parse_gitignore_file(root / ".gitignore", root))

    # Walk and find nested .gitignore files
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip default ignored directories
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".venv", "venv", "vendor"}]

        current = Path(dirpath)
        if current != root and ".gitignore" in filenames:
            all_rules.extend(parse_gitignore_file(current / ".gitignore", current))

    return all_rules


def matches_gitignore(path: Path, is_dir: bool, rules: list[GitIgnoreRule], root: Path) -> bool:
    """Check if a path matches any gitignore rule, respecting negations."""
    matched = False

    for rule in rules:
        # Check if this rule applies to this path
        try:
            rel_to_rule = path.relative_to(rule.source_dir)
        except ValueError:
            continue  # Path not under this rule's directory

        rel_str = str(rel_to_rule)
        name = path.name

        # Skip directory-only rules for files
        if rule.directory_only and not is_dir:
            continue

        # Check pattern match
        pattern = rule.pattern
        does_match = False

        if rule.anchored:
            # Match against relative path from rule's directory
            if fnmatch(rel_str, pattern) or fnmatch(rel_str, pattern + "/**"):
                does_match = True
            # Also try matching path components
            parts = rel_str.split("/")
            for i in range(len(parts)):
                partial = "/".join(parts[:i+1])
                if fnmatch(partial, pattern):
                    does_match = True
                    break
        else:
            # Match against any path component or the name
            if fnmatch(name, pattern):
                does_match = True
            # Also match against full relative path
            elif fnmatch(rel_str, pattern):
                does_match = True
            # Check if pattern matches any component in the path
            else:
                for part in rel_str.split("/"):
                    if fnmatch(part, pattern):
                        does_match = True
                        break

        if does_match:
            matched = not rule.negation

    return matched


def should_ignore(path: Path, is_dir: bool, root: Path, gitignore_rules: list[GitIgnoreRule]) -> bool:
    """Check if a path should be ignored."""
    name = path.name

    # Check default ignores
    for pattern in DEFAULT_IGNORE:
        if "*" in pattern:
            if fnmatch(name, pattern):
                return True
        elif name == pattern:
            return True

    # Check gitignore rules
    if matches_gitignore(path, is_dir, gitignore_rules, root):
        return True

    return False


def count_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    """Count tokens in text using tiktoken."""
    try:
        return len(encoding.encode(text))
    except Exception:
        return len(text) // 4


def is_text_file(path: Path) -> bool:
    """Check if a file is likely a text file."""
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True

    name = path.name.lower()
    if name in TEXT_NAMES:
        return True

    # Try to detect binary by reading first bytes
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return False
            try:
                chunk.decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False
    except Exception:
        return False


def is_generated_file(path: Path, content: str, root: Path) -> bool:
    """Check if a file is generated code."""
    rel_path = str(path.relative_to(root))

    # Path-based detection (exact directory names)
    path_parts = rel_path.lower().split("/")
    for gen_name in GENERATED_PATH_NAMES:
        if gen_name.lower() in path_parts:
            return True

    # Path-based detection (glob patterns like *.egg-info)
    for pattern in GENERATED_PATH_PATTERNS:
        for part in path_parts:
            if fnmatch(part, pattern):
                return True

    # Header-based detection (first 10 lines)
    lines = content.split("\n")[:10]
    header = "\n".join(lines).lower()
    for marker in GENERATED_MARKERS:
        if marker in header:
            return True

    # Content-based signals
    if lines:
        avg_line_length = sum(len(line) for line in lines) / len(lines)
        if avg_line_length > 500:  # Likely minified
            return True

    return False


def count_todos(content: str) -> tuple[int, int]:
    """Count TODO and FIXME occurrences."""
    todo_pattern = re.compile(r"\bTODO\b", re.IGNORECASE)
    fixme_pattern = re.compile(r"\bFIXME\b", re.IGNORECASE)
    return len(todo_pattern.findall(content)), len(fixme_pattern.findall(content))


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def detect_entrypoints(root: Path) -> list[Entrypoint]:
    """Detect codebase entrypoints from config files and conventions."""
    entrypoints = []

    # package.json
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)

            # main field
            if "main" in pkg:
                entrypoints.append(Entrypoint(
                    path=pkg["main"],
                    type="package.json main",
                    evidence=f'"main": "{pkg["main"]}"'
                ))

            # module field
            if "module" in pkg:
                entrypoints.append(Entrypoint(
                    path=pkg["module"],
                    type="package.json module",
                    evidence=f'"module": "{pkg["module"]}"'
                ))

            # bin field
            if "bin" in pkg:
                if isinstance(pkg["bin"], str):
                    entrypoints.append(Entrypoint(
                        path=pkg["bin"],
                        type="package.json bin",
                        evidence=f'"bin": "{pkg["bin"]}"'
                    ))
                elif isinstance(pkg["bin"], dict):
                    for bin_name, bin_path in pkg["bin"].items():
                        entrypoints.append(Entrypoint(
                            path=bin_path,
                            type="package.json bin",
                            evidence=f'"bin": {{"{bin_name}": "{bin_path}"}}'
                        ))

            # exports field (simplified)
            if "exports" in pkg:
                exports = pkg["exports"]
                if isinstance(exports, str):
                    entrypoints.append(Entrypoint(
                        path=exports,
                        type="package.json exports",
                        evidence=f'"exports": "{exports}"'
                    ))
                elif isinstance(exports, dict):
                    for key, val in exports.items():
                        if isinstance(val, str) and key in [".", "./", "import", "require", "default"]:
                            entrypoints.append(Entrypoint(
                                path=val,
                                type="package.json exports",
                                evidence=f'"exports": {{"{key}": ...}}'
                            ))

            # scripts.start
            if "scripts" in pkg and "start" in pkg["scripts"]:
                # Extract file from start script if possible
                start_script = pkg["scripts"]["start"]
                # Common patterns: "node src/index.js", "ts-node src/main.ts", etc.
                match = re.search(r"(?:node|ts-node|tsx|bun)\s+([^\s]+)", start_script)
                if match:
                    entrypoints.append(Entrypoint(
                        path=match.group(1),
                        type="package.json scripts.start",
                        evidence=f'"scripts.start": "{start_script}"'
                    ))

        except (json.JSONDecodeError, KeyError):
            pass

    # pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            # Simple TOML parsing for scripts
            # [project.scripts] or [tool.poetry.scripts]
            script_match = re.findall(r'(\w+)\s*=\s*["\']([^"\']+)["\']', content)
            for name, target in script_match:
                if ":" in target:  # module:function format
                    module = target.split(":")[0].replace(".", "/") + ".py"
                    entrypoints.append(Entrypoint(
                        path=module,
                        type="pyproject.toml scripts",
                        evidence=f'{name} = "{target}"'
                    ))
        except Exception:
            pass

    # Cargo.toml
    cargo = root / "Cargo.toml"
    if cargo.exists():
        try:
            content = cargo.read_text(encoding="utf-8")
            # Look for [[bin]] sections or [lib]
            if "[[bin]]" in content or "src/main.rs" in content:
                if (root / "src" / "main.rs").exists():
                    entrypoints.append(Entrypoint(
                        path="src/main.rs",
                        type="Cargo.toml bin",
                        evidence="Rust binary crate"
                    ))
            if "[lib]" in content or (root / "src" / "lib.rs").exists():
                entrypoints.append(Entrypoint(
                    path="src/lib.rs",
                    type="Cargo.toml lib",
                    evidence="Rust library crate"
                ))
        except Exception:
            pass

    # go.mod + conventions
    go_mod = root / "go.mod"
    if go_mod.exists():
        # Check for cmd/*/main.go
        cmd_dir = root / "cmd"
        if cmd_dir.exists():
            for subdir in cmd_dir.iterdir():
                if subdir.is_dir():
                    main_go = subdir / "main.go"
                    if main_go.exists():
                        rel = str(main_go.relative_to(root))
                        entrypoints.append(Entrypoint(
                            path=rel,
                            type="go convention",
                            evidence="cmd/*/main.go pattern"
                        ))
        # Check for main.go in root
        if (root / "main.go").exists():
            entrypoints.append(Entrypoint(
                path="main.go",
                type="go convention",
                evidence="main.go in root"
            ))

    # Dockerfile
    dockerfile = root / "Dockerfile"
    if dockerfile.exists():
        try:
            content = dockerfile.read_text(encoding="utf-8")
            # Look for CMD or ENTRYPOINT
            for line in content.split("\n"):
                line = line.strip()
                if line.upper().startswith("CMD ") or line.upper().startswith("ENTRYPOINT "):
                    entrypoints.append(Entrypoint(
                        path="Dockerfile",
                        type="Dockerfile",
                        evidence=line[:60] + ("..." if len(line) > 60 else "")
                    ))
                    break
        except Exception:
            pass

    # Makefile
    makefile = root / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text(encoding="utf-8")
            # Look for common targets
            for target in ["run", "start", "serve", "dev"]:
                if re.search(rf"^{target}\s*:", content, re.MULTILINE):
                    entrypoints.append(Entrypoint(
                        path="Makefile",
                        type="Makefile target",
                        evidence=f"make {target}"
                    ))
                    break
        except Exception:
            pass

    # Convention-based detection
    convention_patterns = [
        ("src/index.*", "src/index.{ts,js,tsx,jsx}"),
        ("src/main.*", "src/main.{ts,js,py,rs,go}"),
        ("index.*", "index.{ts,js,tsx,jsx}"),
        ("main.*", "main.{ts,js,py,go}"),
        ("app.*", "app.{ts,js,py}"),
        ("server.*", "server.{ts,js,py}"),
    ]

    for pattern_desc, _ in convention_patterns:
        base = pattern_desc.replace(".*", "")
        for ext in [".ts", ".js", ".tsx", ".jsx", ".py", ".go", ".rs"]:
            candidate = root / (base + ext)
            if candidate.exists():
                rel = str(candidate.relative_to(root))
                # Avoid duplicates
                if not any(e.path == rel for e in entrypoints):
                    entrypoints.append(Entrypoint(
                        path=rel,
                        type="convention",
                        evidence=f"matches {pattern_desc} pattern"
                    ))
                break

    return entrypoints


def detect_config_surface(root: Path, files: list[str]) -> dict[str, list[str]]:
    """Detect configuration files by category."""
    config_surface = defaultdict(list)

    for file_path in files:
        name = Path(file_path).name
        rel_path = file_path

        for category, patterns in CONFIG_PATTERNS.items():
            for pattern in patterns:
                # Handle glob patterns
                if "*" in pattern or "**" in pattern:
                    if fnmatch(rel_path, pattern) or fnmatch(name, pattern):
                        config_surface[category].append(rel_path)
                        break
                else:
                    if name == pattern or rel_path == pattern:
                        config_surface[category].append(rel_path)
                        break

    return dict(config_surface)


def run_git_command(args: list[str], cwd: Path) -> Optional[str]:
    """Run a git command and return output, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return None


def is_git_repo(root: Path) -> bool:
    """Check if root is inside a git repository."""
    return run_git_command(["rev-parse", "--is-inside-work-tree"], root) == "true"


def get_git_churn(root: Path, days: int = 90) -> dict[str, int]:
    """Get commit counts per file in the last N days."""
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    output = run_git_command(
        ["log", f"--since={since_date}", "--name-only", "--pretty=format:"],
        root
    )

    churn = defaultdict(int)
    if output:
        for line in output.split("\n"):
            line = line.strip()
            if line:
                churn[line] += 1

    return dict(churn)


def get_git_staleness(root: Path) -> dict[str, str]:
    """Get last commit date per file."""
    # This is expensive for large repos, so we use a more efficient approach
    # Get all files with their last commit dates
    output = run_git_command(
        ["log", "--format=%H %aI", "--name-only", "--diff-filter=ACMR"],
        root
    )

    staleness = {}
    current_date = None
    if output:
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Check if this is a commit line (hash + date)
            parts = line.split(" ")
            if len(parts) == 2 and len(parts[0]) == 40:
                current_date = parts[1]
            elif current_date and line:
                # This is a file path - only record if we haven't seen it
                if line not in staleness:
                    staleness[line] = current_date

    return staleness


def get_git_cochange(root: Path, min_commits: int = 8, min_ratio: float = 0.6) -> list[dict]:
    """Get files that frequently change together (co-change coupling)."""
    # Get all commits with their files
    output = run_git_command(
        ["log", "--name-only", "--pretty=format:COMMIT"],
        root
    )

    if not output:
        return []

    # Parse commits
    commits = []
    current_files = []
    for line in output.split("\n"):
        line = line.strip()
        if line == "COMMIT":
            if current_files:
                commits.append(set(current_files))
            current_files = []
        elif line:
            current_files.append(line)
    if current_files:
        commits.append(set(current_files))

    # Count co-occurrences
    file_commits = defaultdict(int)
    cochange = defaultdict(int)

    for commit_files in commits:
        files_list = list(commit_files)
        for f in files_list:
            file_commits[f] += 1
        # Count pairs (order-independent)
        for i, f1 in enumerate(files_list):
            for f2 in files_list[i+1:]:
                key = tuple(sorted([f1, f2]))
                cochange[key] += 1

    # Filter and compute ratios
    clusters = []
    seen_pairs = set()

    for (f1, f2), count in sorted(cochange.items(), key=lambda x: -x[1]):
        if count < min_commits:
            continue

        # Compute co-change ratio (symmetric)
        ratio1 = count / file_commits[f1] if file_commits[f1] > 0 else 0
        ratio2 = count / file_commits[f2] if file_commits[f2] > 0 else 0
        ratio = max(ratio1, ratio2)

        if ratio < min_ratio:
            continue

        # Skip expected coupling (test <-> source)
        f1_is_test = "test" in f1.lower() or "spec" in f1.lower()
        f2_is_test = "test" in f2.lower() or "spec" in f2.lower()
        if f1_is_test != f2_is_test:
            # One is test, one is not - expected coupling
            continue

        # Skip types <-> impl coupling
        f1_is_types = "types" in f1.lower() or ".d.ts" in f1
        f2_is_types = "types" in f2.lower() or ".d.ts" in f2
        if f1_is_types != f2_is_types:
            continue

        pair_key = tuple(sorted([f1, f2]))
        if pair_key not in seen_pairs:
            seen_pairs.add(pair_key)
            clusters.append({
                "files": [f1, f2],
                "commits": count,
                "ratio": round(ratio, 2),
            })

    # Return top 10
    return clusters[:10]


def scan_directory(
    root: Path,
    encoding: tiktoken.Encoding,
    max_file_tokens: int = 50000,
    include_patterns: list[str] = None,
    exclude_patterns: list[str] = None,
    extensions: list[str] = None,
    top_n: int = None,
    sort_by: str = "tokens",
) -> ScanResult:
    """
    Scan a directory and return comprehensive codebase metadata.
    """
    root = root.resolve()
    gitignore_rules = collect_gitignore_rules(root)

    files = []
    directories = []
    skipped = []
    total_tokens = 0
    content_hashes = defaultdict(list)
    generated_files = []
    todo_total = 0
    fixme_total = 0
    todo_by_dir = defaultdict(int)

    # Check git availability
    git_available = is_git_repo(root)
    git_churn = {}
    git_staleness = {}

    if git_available:
        git_churn = get_git_churn(root)
        git_staleness = get_git_staleness(root)

    def should_include(rel_path: str) -> bool:
        """Check if file matches include/exclude/extension filters."""
        # Check extensions filter
        if extensions:
            suffix = Path(rel_path).suffix.lower()
            if suffix not in extensions and suffix.lstrip(".") not in extensions:
                return False

        # Check include patterns
        if include_patterns:
            if not any(fnmatch(rel_path, p) for p in include_patterns):
                return False

        # Check exclude patterns
        if exclude_patterns:
            if any(fnmatch(rel_path, p) for p in exclude_patterns):
                return False

        return True

    def walk(current: Path, depth: int = 0):
        nonlocal total_tokens, todo_total, fixme_total

        if should_ignore(current, current.is_dir(), root, gitignore_rules):
            return

        if current.is_dir():
            rel_path = str(current.relative_to(root))
            if rel_path != ".":
                directories.append(rel_path)

            try:
                entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                for entry in entries:
                    walk(entry, depth + 1)
            except PermissionError:
                skipped.append({"path": str(current.relative_to(root)), "reason": "permission_denied"})

        elif current.is_file():
            rel_path = str(current.relative_to(root))

            # Apply filters
            if not should_include(rel_path):
                return

            try:
                size_bytes = current.stat().st_size
            except OSError:
                skipped.append({"path": rel_path, "reason": "stat_error"})
                return

            # Skip very large files
            if size_bytes > 1_000_000:  # 1MB
                skipped.append({"path": rel_path, "reason": "too_large", "size_bytes": size_bytes})
                return

            if not is_text_file(current):
                skipped.append({"path": rel_path, "reason": "binary"})
                return

            try:
                with open(current, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                tokens = count_tokens(content, encoding)

                if tokens > max_file_tokens:
                    skipped.append({"path": rel_path, "reason": "too_many_tokens", "tokens": tokens})
                    return

                # Compute hash for duplicate detection
                content_hash = compute_content_hash(content)
                content_hashes[content_hash].append(rel_path)

                # Check if generated
                is_gen = is_generated_file(current, content, root)
                if is_gen:
                    generated_files.append(rel_path)

                # Count TODOs/FIXMEs
                todos, fixmes = count_todos(content)
                todo_total += todos
                fixme_total += fixmes
                if todos > 0 or fixmes > 0:
                    parent_dir = str(Path(rel_path).parent)
                    todo_by_dir[parent_dir] += todos + fixmes

                # Git info
                git_commits = git_churn.get(rel_path, 0)
                last_commit = git_staleness.get(rel_path)

                file_info = FileInfo(
                    path=rel_path,
                    tokens=tokens,
                    size_bytes=size_bytes,
                    content_hash=content_hash,
                    is_generated=is_gen,
                    todo_count=todos,
                    fixme_count=fixmes,
                    git_commits_90d=git_commits,
                    git_last_commit=last_commit,
                )

                files.append(file_info)
                total_tokens += tokens

            except Exception as e:
                skipped.append({"path": rel_path, "reason": f"read_error: {str(e)}"})

    walk(root)

    # Find duplicates (files with same hash)
    duplicates = {h: paths for h, paths in content_hashes.items() if len(paths) > 1}

    # Detect entrypoints
    entrypoints = detect_entrypoints(root)

    # Detect config surface
    all_file_paths = [f.path for f in files]
    config_surface = detect_config_surface(root, all_file_paths)

    # Get co-change coupling if git available
    cochange_clusters = []
    if git_available:
        cochange_clusters = get_git_cochange(root)

    # Sort files
    if sort_by == "churn" and git_available:
        files.sort(key=lambda f: f.git_commits_90d, reverse=True)
    else:
        files.sort(key=lambda f: f.tokens, reverse=True)

    # Apply top_n filter
    if top_n:
        files = files[:top_n]

    # Convert FileInfo to dicts for JSON serialization
    files_dicts = []
    for f in files:
        d = {
            "path": f.path,
            "tokens": f.tokens,
            "size_bytes": f.size_bytes,
        }
        if f.content_hash:
            d["content_hash"] = f.content_hash
        if f.is_generated:
            d["is_generated"] = True
        if f.todo_count > 0:
            d["todo_count"] = f.todo_count
        if f.fixme_count > 0:
            d["fixme_count"] = f.fixme_count
        if f.git_commits_90d > 0:
            d["git_commits_90d"] = f.git_commits_90d
        if f.git_last_commit:
            d["git_last_commit"] = f.git_last_commit
        files_dicts.append(d)

    # Git stats summary
    git_stats = {}
    if git_available:
        # Find hotspots (high churn)
        hotspots = sorted(
            [(p, c) for p, c in git_churn.items() if c >= 5],
            key=lambda x: -x[1]
        )[:20]
        git_stats["hotspots"] = [{"path": p, "commits_90d": c} for p, c in hotspots]

        # Find stale files (no commits in 6+ months)
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
        stale_files = []
        for path, date_str in git_staleness.items():
            try:
                last_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if last_date < six_months_ago:
                    days_stale = (datetime.now(timezone.utc) - last_date).days
                    stale_files.append({"path": path, "last_commit": date_str, "days_stale": days_stale})
            except (ValueError, TypeError):
                pass
        git_stats["stale_files"] = sorted(stale_files, key=lambda x: -x["days_stale"])[:20]

        # Co-change coupling
        git_stats["cochange_clusters"] = cochange_clusters

    # Todo summary
    todo_summary = {
        "total_todos": todo_total,
        "total_fixmes": fixme_total,
        "by_directory": dict(sorted(todo_by_dir.items(), key=lambda x: -x[1])[:10]),
    }

    return ScanResult(
        root=str(root),
        scanner_version=SCANNER_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        args={
            "max_file_tokens": max_file_tokens,
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "extensions": extensions,
            "top_n": top_n,
            "sort_by": sort_by,
        },
        files=files_dicts,
        directories=directories,
        total_tokens=total_tokens,
        total_files=len(files_dicts),
        skipped=skipped,
        entrypoints=[{"path": e.path, "type": e.type, "evidence": e.evidence} for e in entrypoints],
        config_surface=config_surface,
        duplicates={h: paths for h, paths in duplicates.items()},
        git_available=git_available,
        git_stats=git_stats,
        generated_files=generated_files,
        todo_summary=todo_summary,
    )


def format_tree(result: ScanResult, show_tokens: bool = True) -> str:
    """Format scan results as a tree structure."""
    lines = []
    root_name = Path(result.root).name
    lines.append(f"{root_name}/")
    lines.append(f"Scanner v{result.scanner_version} | {result.timestamp}")
    lines.append(f"Total: {result.total_files} files, {result.total_tokens:,} tokens")
    if result.git_available:
        lines.append("Git: available")
    lines.append("")

    # Build tree structure
    tree: dict = {}
    for f in result.files:
        parts = Path(f["path"]).parts
        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = f

    def print_tree(node: dict, prefix: str = ""):
        items = sorted(node.items(), key=lambda x: (not isinstance(x[1], dict) or "tokens" in x[1], x[0].lower()))

        for i, (name, value) in enumerate(items):
            is_last_item = i == len(items) - 1
            connector = "└── " if is_last_item else "├── "

            if isinstance(value, dict) and "tokens" not in value:
                lines.append(f"{prefix}{connector}{name}/")
                extension = "    " if is_last_item else "│   "
                print_tree(value, prefix + extension)
            else:
                if show_tokens:
                    tokens = value.get("tokens", 0)
                    extras = []
                    if value.get("is_generated"):
                        extras.append("gen")
                    if value.get("git_commits_90d", 0) > 10:
                        extras.append(f"churn:{value['git_commits_90d']}")
                    extra_str = f" [{', '.join(extras)}]" if extras else ""
                    lines.append(f"{prefix}{connector}{name} ({tokens:,} tokens){extra_str}")
                else:
                    lines.append(f"{prefix}{connector}{name}")

    print_tree(tree)
    return "\n".join(lines)


def result_to_dict(result: ScanResult) -> dict:
    """Convert ScanResult to a dictionary for JSON serialization."""
    return {
        "root": result.root,
        "scanner_version": result.scanner_version,
        "timestamp": result.timestamp,
        "args": result.args,
        "files": result.files,
        "directories": result.directories,
        "total_tokens": result.total_tokens,
        "total_files": result.total_files,
        "skipped": result.skipped,
        "entrypoints": result.entrypoints,
        "config_surface": result.config_surface,
        "duplicates": result.duplicates,
        "git_available": result.git_available,
        "git_stats": result.git_stats,
        "generated_files": result.generated_files,
        "todo_summary": result.todo_summary,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Scan a codebase and output comprehensive metadata for Recon"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "tree", "compact"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=50000,
        help="Skip files with more than this many tokens (default: 50000)",
    )
    parser.add_argument(
        "--encoding",
        default="cl100k_base",
        help="Tiktoken encoding to use (default: cl100k_base)",
    )
    parser.add_argument(
        "--top",
        type=int,
        dest="top_n",
        help="Show only top N files",
    )
    parser.add_argument(
        "--sort",
        choices=["tokens", "churn"],
        default="tokens",
        help="Sort files by tokens or git churn (default: tokens)",
    )
    parser.add_argument(
        "--ext",
        dest="extensions",
        help="Filter by extensions (comma-separated, e.g., '.ts,.tsx')",
    )
    parser.add_argument(
        "--include",
        dest="include_patterns",
        help="Include glob patterns (comma-separated, e.g., 'src/**')",
    )
    parser.add_argument(
        "--exclude",
        dest="exclude_patterns",
        help="Exclude glob patterns (comma-separated, e.g., 'test/**')",
    )

    args = parser.parse_args()
    path = Path(args.path).resolve()

    if not path.exists():
        print(f"ERROR: Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if not path.is_dir():
        print(f"ERROR: Path is not a directory: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        encoding = tiktoken.get_encoding(args.encoding)
    except Exception as e:
        print(f"ERROR: Failed to load encoding '{args.encoding}': {e}", file=sys.stderr)
        sys.exit(1)

    # Parse filter arguments
    extensions = None
    if args.extensions:
        extensions = [e.strip() for e in args.extensions.split(",")]

    include_patterns = None
    if args.include_patterns:
        include_patterns = [p.strip() for p in args.include_patterns.split(",")]

    exclude_patterns = None
    if args.exclude_patterns:
        exclude_patterns = [p.strip() for p in args.exclude_patterns.split(",")]

    result = scan_directory(
        path,
        encoding,
        max_file_tokens=args.max_tokens,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        extensions=extensions,
        top_n=args.top_n,
        sort_by=args.sort,
    )

    if args.format == "json":
        print(json.dumps(result_to_dict(result), indent=2))
    elif args.format == "tree":
        print(format_tree(result, show_tokens=True))
    elif args.format == "compact":
        print(f"# {result.root}")
        print(f"# Scanner v{result.scanner_version} | {result.timestamp}")
        print(f"# Total: {result.total_files} files, {result.total_tokens:,} tokens")
        print()
        for f in result.files:
            extras = []
            if f.get("is_generated"):
                extras.append("gen")
            if f.get("git_commits_90d", 0) > 0:
                extras.append(f"churn:{f['git_commits_90d']}")
            extra_str = f"  [{', '.join(extras)}]" if extras else ""
            print(f"{f['tokens']:>8} {f['path']}{extra_str}")


if __name__ == "__main__":
    main()
