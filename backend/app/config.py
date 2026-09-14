from functools import lru_cache
from pathlib import Path
from typing import Literal

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

    llm_provider: Literal["auto", "anthropic", "openai"] = "auto"
    llm_model: str | None = None
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = "high"
    llm_max_output_tokens: int = 32_000
    llm_concurrency: int = 4
    llm_max_attempts: int = 3
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    database_url: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'data' / 'reviewmind.db'}"
    # Fernet key that encrypts stored GitHub tokens. Leave unset locally and one is
    # generated into data/secret.key; set it explicitly anywhere else.
    secret_key: SecretStr | None = None
    secret_key_file: Path = BACKEND_DIR / "data" / "secret.key"
    github_webhook_secret: SecretStr | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Assumption behind the "time saved" stat: a careful first-pass human review of one
    # changed file. Surfaced in the UI next to the number so it isn't mistaken for a measurement.
    minutes_per_file_manual_review: float = 6.0

    @property
    def github_token_value(self) -> str | None:
        return _secret(self.github_token)

    @property
    def anthropic_api_key_value(self) -> str | None:
        return _secret(self.anthropic_api_key)

    @property
    def openai_api_key_value(self) -> str | None:
        return _secret(self.openai_api_key)


def _secret(value: SecretStr | None) -> str | None:
    if value is None:
        return None
    return value.get_secret_value().strip() or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
