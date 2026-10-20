"""Swappable LLM providers for grounded (retrieval-augmented) answers.

Select with NURU_LLM_PROVIDER:
  none       offline mode (default): return the best retrieved library answer as is
  openai     OpenAI Chat Completions   (needs OPENAI_API_KEY)
  anthropic  Anthropic Messages API    (needs ANTHROPIC_API_KEY)
  gemini     Google Gemini API         (needs GEMINI_API_KEY)

Override the model with NURU_LLM_MODEL. Adapters call the HTTP APIs directly
with httpx so no vendor SDK is required.

Safety contract for every provider:
  * the LLM only ever sees the user's question (phone numbers redacted) and the
    retrieved, clinician-reviewed passages, never the phone number or history;
  * it is told to answer only from those passages, in Kiswahili, without
    diagnosing; if the passages do not answer, it must refer to a facility;
  * any error, timeout or empty output falls back to the library answer;
  * the LLM is never called for red-flag or safeguarding messages (the router
    returns before reaching this module).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from .retrieval import ContentEntry

log = logging.getLogger("nuru.llm")

SYSTEM_PROMPT = """You are NURU, a free SMS health education service for girls, women and parents in Tanzania.
Rules you must follow:
1. Answer ONLY using the reference passages provided. They are written and reviewed by doctors.
2. Reply in simple Kiswahili that a young person with primary education understands.
3. Maximum {max_chars} characters. Plain text only, no lists, no emoji, no links.
4. Never diagnose, never say what the person "has", never give drug doses that are not in the passages.
5. If the passages do not answer the question, say you are not sure and advise visiting the nearest health facility.
6. Do not repeat personal details from the question. Be warm, short and non-judgemental.
7. Myths: say clearly that it is not true, then give the correct fact from the passages."""

USER_TEMPLATE = """Reference passages:
{passages}

Question from SMS user:
{question}

Write the SMS reply now."""

_PHONE = re.compile(r"\+?\d[\d\s-]{7,}\d")


def redact(text: str) -> str:
    """Remove phone-number-like digit runs before text leaves our system."""
    return _PHONE.sub("[namba]", text)


def build_prompt(question: str, passages: list[ContentEntry], max_chars: int) -> tuple[str, str]:
    joined = "\n".join(f"[{i + 1}] ({p.id}) {p.answer_sw}" for i, p in enumerate(passages))
    return (
        SYSTEM_PROMPT.format(max_chars=max_chars),
        USER_TEMPLATE.format(passages=joined, question=redact(question)),
    )


class LLMProvider(Protocol):
    name: str

    def generate(self, question: str, passages: list[ContentEntry], max_chars: int) -> str: ...


@dataclass
class OfflineProvider:
    """No AI: return the top retrieved answer verbatim. Safest, and works with no key."""

    name: str = "none"

    def generate(self, question: str, passages: list[ContentEntry], max_chars: int) -> str:
        return passages[0].answer_sw if passages else ""


@dataclass
class OpenAIProvider:
    api_key: str
    model: str = "gpt-4o-mini"
    timeout: float = 15.0
    base_url: str = "https://api.openai.com/v1"
    name: str = "openai"

    def generate(self, question: str, passages: list[ContentEntry], max_chars: int) -> str:
        system, user = build_prompt(question, passages, max_chars)
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_completion_tokens": 300,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""


@dataclass
class AnthropicProvider:
    api_key: str
    model: str = "claude-haiku-5-5"
    timeout: float = 15.0
    base_url: str = "https://api.anthropic.com/v1"
    name: str = "anthropic"

    def generate(self, question: str, passages: list[ContentEntry], max_chars: int) -> str:
        system, user = build_prompt(question, passages, max_chars)
        resp = httpx.post(
            f"{self.base_url}/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.model,
                "max_tokens": 300,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


@dataclass
class GeminiProvider:
    api_key: str
    model: str = "gemini-2.5-flash"
    timeout: float = 15.0
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    name: str = "gemini"

    def generate(self, question: str, passages: list[ContentEntry], max_chars: int) -> str:
        system, user = build_prompt(question, passages, max_chars)
        resp = httpx.post(
            f"{self.base_url}/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": 300},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)


def get_provider(name: str | None = None, model: str | None = None, timeout: float = 15.0) -> LLMProvider:
    """Build the provider named by NURU_LLM_PROVIDER. Missing keys fall back to offline mode."""
    name = (name or os.getenv("NURU_LLM_PROVIDER", "none")).strip().lower()
    model = (model if model is not None else os.getenv("NURU_LLM_MODEL", "")).strip()

    table = {
        "openai": (OpenAIProvider, "OPENAI_API_KEY"),
        "anthropic": (AnthropicProvider, "ANTHROPIC_API_KEY"),
        "claude": (AnthropicProvider, "ANTHROPIC_API_KEY"),
        "gemini": (GeminiProvider, "GEMINI_API_KEY"),
        "google": (GeminiProvider, "GEMINI_API_KEY"),
    }
    if name in {"", "none", "offline", "fallback"}:
        return OfflineProvider()
    if name not in table:
        log.warning("Unknown NURU_LLM_PROVIDER=%r, using offline mode", name)
        return OfflineProvider()

    cls, key_var = table[name]
    api_key = os.getenv(key_var, "").strip()
    if not api_key:
        log.warning("%s is not set, using offline mode", key_var)
        return OfflineProvider()
    kwargs = {"api_key": api_key, "timeout": timeout}
    if model:
        kwargs["model"] = model
    return cls(**kwargs)


@dataclass
class GroundedAnswer:
    text: str
    source: str  # "llm:<provider>" or "library"


def grounded_answer(
    provider: LLMProvider, question: str, passages: list[ContentEntry], max_chars: int
) -> GroundedAnswer:
    """Ask the provider for an answer; on any failure return the library answer."""
    if not passages:
        return GroundedAnswer(text="", source="library")
    library = passages[0].answer_sw
    if isinstance(provider, OfflineProvider):
        return GroundedAnswer(text=library, source="library")
    try:
        text = (provider.generate(question, passages, max_chars) or "").strip()
    except Exception as exc:  # network, quota, schema change: never fail the user
        log.warning("LLM provider %s failed (%s); using library answer", provider.name, type(exc).__name__)
        return GroundedAnswer(text=library, source="library")
    if not text:
        return GroundedAnswer(text=library, source="library")
    return GroundedAnswer(text=text, source=f"llm:{provider.name}")
