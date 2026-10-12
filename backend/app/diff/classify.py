"""Decide which changed files are worth an LLM's attention, and what language they are.

Path heuristics are deliberately conservative: skipping a real source file costs review
coverage, while reviewing a lockfile only costs tokens, so anything ambiguous is reviewed.
"""

from pathlib import PurePosixPath

from app.diff.models import SkipReason

LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock",
        "bun.lockb", "deno.lock", "poetry.lock", "pipfile.lock", "uv.lock", "pdm.lock",
        "cargo.lock", "go.sum", "gemfile.lock", "composer.lock", "mix.lock", "pubspec.lock",
        "podfile.lock", "packages.lock.json", "package.resolved", "flake.lock", "gradle.lockfile",
    }
)

VENDORED_DIRS = frozenset({"vendor", "node_modules", "third_party", "bower_components", ".yarn"})
GENERATED_DIRS = frozenset(
    {"dist", "build", "out", ".next", ".nuxt", "coverage", "__generated__", "__snapshots__", "generated"}
)
GENERATED_SUFFIXES = (
    ".min.js", ".min.css", ".map", ".pb.go", "_pb2.py", "_pb2_grpc.py", ".g.dart",
    ".freezed.dart", ".snap", ".designer.cs", ".generated.ts", ".generated.js",
)

ASSET_EXTENSIONS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".bmp", ".tiff", ".svg",
        ".psd", ".mp3", ".mp4", ".wav", ".ogg", ".mov", ".webm", ".woff", ".woff2", ".ttf",
        ".otf", ".eot", ".pdf", ".zip", ".gz", ".tgz", ".tar", ".7z", ".rar", ".jar", ".war",
        ".exe", ".dll", ".so", ".dylib", ".bin", ".wasm", ".pyc", ".class", ".sqlite", ".db",
        ".parquet", ".pkl", ".onnx",
    }
)

DOC_EXTENSIONS = frozenset({".md", ".mdx", ".rst", ".adoc", ".txt"})
DOC_FILENAMES = frozenset({"license", "licence", "notice", "authors", "contributors"})

LANGUAGE_BY_FILENAME = {
    "dockerfile": "dockerfile", "containerfile": "dockerfile", "makefile": "makefile",
    "gnumakefile": "makefile", "cmakelists.txt": "cmake", "gemfile": "ruby", "rakefile": "ruby",
    "podfile": "ruby", "vagrantfile": "ruby", "jenkinsfile": "groovy",
}

LANGUAGE_BY_EXTENSION = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".jsx": "jsx", ".ts": "typescript", ".mts": "typescript",
    ".cts": "typescript", ".tsx": "tsx", ".go": "go", ".rs": "rust", ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala", ".rb": "ruby", ".php": "php",
    ".cs": "csharp", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp", ".swift": "swift", ".m": "objective-c", ".mm": "objective-c",
    ".dart": "dart", ".lua": "lua", ".r": "r", ".jl": "julia", ".ex": "elixir", ".exs": "elixir",
    ".erl": "erlang", ".hs": "haskell", ".clj": "clojure", ".zig": "zig", ".nix": "nix",
    ".sol": "solidity", ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".ps1": "powershell",
    ".sql": "sql", ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
    ".sass": "sass", ".less": "less", ".vue": "vue", ".svelte": "svelte", ".astro": "astro",
    ".json": "json", ".jsonc": "json", ".ipynb": "json", ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini", ".xml": "xml", ".graphql": "graphql",
    ".gql": "graphql", ".proto": "protobuf", ".tf": "hcl", ".hcl": "hcl", ".gradle": "groovy",
    ".groovy": "groovy", ".md": "markdown", ".mdx": "mdx", ".rst": "rst", ".txt": "text",
}


def classify_path(filename: str) -> SkipReason | None:
    """Return why a file should be skipped based on its path alone, or None to review it."""
    path = PurePosixPath(filename)
    name = path.name.lower()
    directories = {part.lower() for part in path.parts[:-1]}
    suffix = path.suffix.lower()

    if directories & VENDORED_DIRS:
        return SkipReason.VENDORED
    if name in LOCKFILE_NAMES or name.endswith(".lock"):
        return SkipReason.LOCKFILE
    if directories & GENERATED_DIRS or name.endswith(GENERATED_SUFFIXES):
        return SkipReason.GENERATED
    if suffix in ASSET_EXTENSIONS:
        return SkipReason.ASSET
    if (suffix in DOC_EXTENSIONS and not _is_build_manifest(name)) or name in DOC_FILENAMES:
        return SkipReason.DOCS
    return None


def detect_language(filename: str) -> str:
    path = PurePosixPath(filename)
    name = path.name.lower()
    if name in LANGUAGE_BY_FILENAME:
        return LANGUAGE_BY_FILENAME[name]
    if name.startswith("dockerfile"):
        return "dockerfile"
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "text")


def _is_build_manifest(name: str) -> bool:
    # .txt files that pin dependencies or drive builds are worth reviewing (pinning, CVEs).
    return name.startswith(("requirements", "constraints")) or name == "cmakelists.txt"
