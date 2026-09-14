import pytest

from app.diff.classify import classify_path, detect_language
from app.diff.models import SkipReason


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("package-lock.json", SkipReason.LOCKFILE),
        ("frontend/yarn.lock", SkipReason.LOCKFILE),
        ("backend/uv.lock", SkipReason.LOCKFILE),
        ("go.sum", SkipReason.LOCKFILE),
        ("Cargo.lock", SkipReason.LOCKFILE),
        ("vendor/github.com/pkg/errors/errors.go", SkipReason.VENDORED),
        ("web/node_modules/left-pad/index.js", SkipReason.VENDORED),
        ("dist/bundle.js", SkipReason.GENERATED),
        ("static/app.min.js", SkipReason.GENERATED),
        ("api/users_pb2.py", SkipReason.GENERATED),
        ("src/__snapshots__/Button.test.tsx.snap", SkipReason.GENERATED),
        ("public/logo.png", SkipReason.ASSET),
        ("assets/fonts/Inter.woff2", SkipReason.ASSET),
        ("icons/check.svg", SkipReason.ASSET),
        ("README.md", SkipReason.DOCS),
        ("docs/guide.rst", SkipReason.DOCS),
        ("LICENSE", SkipReason.DOCS),
    ],
)
def test_noise_files_are_skipped(filename, expected):
    assert classify_path(filename) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "src/app.py",
        "web/src/components/Button.tsx",
        ".github/workflows/ci.yml",
        "requirements.txt",
        "requirements-dev.txt",
        "CMakeLists.txt",
        "Dockerfile",
        "docs_src/tutorial001.py",
        "src/build_utils.py",
        "migrations/0004_add_index.sql",
    ],
)
def test_source_and_config_files_are_reviewed(filename):
    assert classify_path(filename) is None


@pytest.mark.parametrize(
    ("filename", "language"),
    [
        ("app/main.py", "python"),
        ("src/App.tsx", "tsx"),
        ("src/index.mjs", "javascript"),
        ("cmd/server/main.go", "go"),
        ("Dockerfile", "dockerfile"),
        ("Dockerfile.prod", "dockerfile"),
        ("Makefile", "makefile"),
        (".github/workflows/ci.YML", "yaml"),
        ("LICENSE", "text"),
    ],
)
def test_language_detection(filename, language):
    assert detect_language(filename) == language
