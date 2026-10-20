"""Runtime configuration, read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # python-dotenv is optional; the service runs without it.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # LLM
    llm_provider: str = field(default_factory=lambda: os.getenv("NURU_LLM_PROVIDER", "none").strip().lower())
    llm_model: str = field(default_factory=lambda: os.getenv("NURU_LLM_MODEL", "").strip())
    llm_timeout: float = field(default_factory=lambda: _float("NURU_LLM_TIMEOUT", 15.0))

    # Retrieval
    content_dir: Path = field(default_factory=lambda: Path(os.getenv("NURU_CONTENT_DIR", ROOT_DIR / "content")))
    min_retrieval_score: float = field(default_factory=lambda: _float("NURU_MIN_RETRIEVAL_SCORE", 0.12))

    # Facility finder
    facilities_csv: Path = field(
        default_factory=lambda: Path(os.getenv("NURU_FACILITIES_CSV", ROOT_DIR / "data" / "facilities_sample.csv"))
    )

    # SMS
    max_reply_chars: int = field(default_factory=lambda: _int("NURU_MAX_REPLY_CHARS", 306))
    at_username: str = field(default_factory=lambda: os.getenv("AT_USERNAME", "sandbox"))
    at_api_key: str = field(default_factory=lambda: os.getenv("AT_API_KEY", ""))
    at_shortcode: str = field(default_factory=lambda: os.getenv("AT_SHORTCODE", ""))
    sms_dry_run: bool = field(default_factory=lambda: _bool("NURU_SMS_DRY_RUN", True))

    # Webhook
    webhook_token: str = field(default_factory=lambda: os.getenv("NURU_WEBHOOK_TOKEN", ""))
    phone_hash_salt: str = field(default_factory=lambda: os.getenv("NURU_PHONE_HASH_SALT", "change-me"))


def get_settings() -> Settings:
    return Settings()
