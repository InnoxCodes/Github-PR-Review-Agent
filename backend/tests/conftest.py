import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        github_token=None,
        max_changed_lines_per_file=50,
        max_reviewable_files=3,
        chunk_max_lines=20,
    )
