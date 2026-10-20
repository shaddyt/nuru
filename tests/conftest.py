import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nuru.config import Settings  # noqa: E402
from nuru.facility import FacilityFinder  # noqa: E402
from nuru.llm import OfflineProvider  # noqa: E402
from nuru.retrieval import Retriever  # noqa: E402
from nuru.router import Router  # noqa: E402


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    """Tests never call a real LLM or send a real SMS."""
    monkeypatch.setenv("NURU_LLM_PROVIDER", "none")
    monkeypatch.setenv("NURU_SMS_DRY_RUN", "true")
    monkeypatch.delenv("NURU_WEBHOOK_TOKEN", raising=False)


@pytest.fixture
def settings():
    return Settings(
        llm_provider="none",
        content_dir=ROOT / "content",
        facilities_csv=ROOT / "data" / "facilities_sample.csv",
        sms_dry_run=True,
        webhook_token="",
    )


@pytest.fixture
def retriever(settings):
    return Retriever.from_dir(settings.content_dir)


@pytest.fixture
def finder(settings):
    return FacilityFinder.from_csv(settings.facilities_csv)


@pytest.fixture
def router(settings, retriever, finder):
    return Router(retriever=retriever, finder=finder, provider=OfflineProvider(), settings=settings)
