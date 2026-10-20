"""Provider selection and adapter parsing, with the network mocked out."""

import pytest

from nuru import llm
from nuru.retrieval import ContentEntry

PASSAGE = ContentEntry(
    id="t1", topic="t", life_stage="x", type="faq", questions=["q"], keywords=[], answer_sw="Jibu la maktaba."
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    "name,key_var,cls",
    [
        ("openai", "OPENAI_API_KEY", llm.OpenAIProvider),
        ("anthropic", "ANTHROPIC_API_KEY", llm.AnthropicProvider),
        ("gemini", "GEMINI_API_KEY", llm.GeminiProvider),
    ],
)
def test_provider_selected_by_env(monkeypatch, name, key_var, cls):
    monkeypatch.setenv(key_var, "test-key")
    assert isinstance(llm.get_provider(name, ""), cls)


def test_missing_key_falls_back_to_offline(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(llm.get_provider("openai", ""), llm.OfflineProvider)


def test_unknown_and_none_are_offline():
    assert isinstance(llm.get_provider("none", ""), llm.OfflineProvider)
    assert isinstance(llm.get_provider("banana", ""), llm.OfflineProvider)


def test_model_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert llm.get_provider("anthropic", "my-model").model == "my-model"


@pytest.mark.parametrize(
    "provider,payload",
    [
        (llm.OpenAIProvider(api_key="k"), {"choices": [{"message": {"content": "Jibu."}}]}),
        (llm.AnthropicProvider(api_key="k"), {"content": [{"type": "text", "text": "Jibu."}]}),
        (llm.GeminiProvider(api_key="k"), {"candidates": [{"content": {"parts": [{"text": "Jibu."}]}}]}),
    ],
)
def test_adapters_parse_responses(monkeypatch, provider, payload):
    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["url"], sent["json"] = url, json
        return FakeResponse(payload)

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert provider.generate("swali +255 712 345 678", [PASSAGE], 306) == "Jibu."
    body = str(sent["json"])
    assert "Jibu la maktaba." in body  # grounded on the passage
    assert "712 345 678" not in body  # phone numbers redacted


def test_offline_returns_library_answer():
    out = llm.grounded_answer(llm.OfflineProvider(), "swali", [PASSAGE], 306)
    assert out.text == "Jibu la maktaba." and out.source == "library"


def test_empty_llm_output_falls_back():
    class Empty:
        name = "empty"

        def generate(self, *a):
            return "   "

    out = llm.grounded_answer(Empty(), "swali", [PASSAGE], 306)
    assert out.source == "library"
