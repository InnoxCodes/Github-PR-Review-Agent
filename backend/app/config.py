from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    github_token: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_timeout_seconds: float = 20.0

    # Past ~1.5k changed lines a single file is almost always generated or vendored,
    # and LLM review quality on it collapses — skip it and say so instead of chunking.
    max_changed_lines_per_file: int = 1500
    max_reviewable_files: int = 40
    chunk_max_lines: int = 400

    @property
    def github_token_value(self) -> str | None:
        if self.github_token is None:
            return None
        return self.github_token.get_secret_value() or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
