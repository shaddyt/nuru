"""Message orchestration. The order is fixed and safety-critical:

  1. red-flag and safeguarding screen  -> fixed message, STOP (no AI)
  2. commands (MSAADA/HELP, STOP)
  3. facility intent or pending location -> facility finder
  4. retrieval over the content library -> grounded answer (LLM or library)
  5. nothing relevant found -> safe fallback that points to a facility

Every reply passes through fit_sms so it is GSM-7 and at most 2 SMS.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

from . import red_flags
from .config import Settings, get_settings
from .facility import FacilityFinder, extract_place, format_facility_reply
from .formatting import fit_sms, segment_count
from .llm import LLMProvider, get_provider, grounded_answer
from .retrieval import Retriever
from .sms import hash_phone
from .textnorm import normalise

WELCOME = (
    "Karibu NURU, huduma ya bure ya elimu ya afya kwa SMS. Uliza swali lolote kuhusu hedhi, "
    "uzazi wa mpango, magonjwa ya zinaa, ujauzito au mtoto mchanga. Kupata kituo cha afya, tuma "
    "KITUO na jina la kata yako. Kusitisha, tuma STOP."
)
STOPPED = "Umesitisha ujumbe wa NURU. Kurudi wakati wowote, tuma MSAADA. Asante."
ASK_LOCATION = (
    "Tuma jina la kata au kijiji chako, kwa mfano: Makole. NURU haihifadhi mahali ulipo."
)
FACILITY_NOT_FOUND = (
    "Samahani, hatukupata kata au kijiji hicho. Angalia tahajia au tuma jina la kata jirani. "
    "Kwa dharura, nenda kituo cha afya kilicho karibu nawe sasa."
)
FALLBACK = (
    "Samahani, sina jibu la uhakika kwa swali hili. Tafadhali muone mtaalamu wa afya kwenye "
    "kituo kilicho karibu. Tuma KITUO na jina la kata yako kupata kituo. Unaweza pia kuuliza "
    "kwa maneno mengine."
)

_HELP = {"msaada", "help", "menu", "anza", "start", "habari", "hi", "hello", "mambo", "nuru"}
_STOP = {"stop", "acha", "sitisha", "unsubscribe"}
_FACILITY_KEYWORD = re.compile(r"^(kituo|vituo|facility|clinic)\b")
_FACILITY_WORD = re.compile(r"\b(kituo|vituo|hospitali|zahanati|kliniki|clinic|facility|hospital)\b")
_LOCATION_STATEMENT = re.compile(r"\b(kata|kijiji|mtaa|naishi|nipo|niko|ward|village)\b")
_NEAR_WORD = re.compile(r"\b(karibu|nearest|near|wapi|where|kilicho)\b")

SESSION_TTL_SECONDS = 15 * 60


@dataclass
class Reply:
    text: str
    category: str  # red_flag | safeguarding | facility | answer | fallback | menu | stop
    rule_id: Optional[str] = None
    content_ids: list[str] = field(default_factory=list)
    source: Optional[str] = None
    retrieval_score: Optional[float] = None

    @property
    def segments(self) -> int:
        return segment_count(self.text)


class SessionStore:
    """Minimal in-memory state keyed by a salted phone hash.

    Holds only a pending-step flag with an expiry. No message text, no
    location, no history. Swap for Redis in production; RapidPro can also own
    this state in its flows.
    """

    def __init__(self, ttl: int = SESSION_TTL_SECONDS):
        self.ttl = ttl
        self._data: dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> Optional[str]:
        item = self._data.get(key)
        if not item:
            return None
        state, expires = item
        if time.time() > expires:
            self._data.pop(key, None)
            return None
        return state

    def set(self, key: str, state: str) -> None:
        self._data[key] = (state, time.time() + self.ttl)

    def clear(self, key: str) -> None:
        self._data.pop(key, None)


class Router:
    def __init__(
        self,
        retriever: Retriever,
        finder: FacilityFinder,
        provider: LLMProvider,
        settings: Optional[Settings] = None,
        sessions: Optional[SessionStore] = None,
    ):
        self.settings = settings or get_settings()
        self.retriever = retriever
        self.finder = finder
        self.provider = provider
        self.sessions = sessions or SessionStore()
        self.sample_facility_data = "sample" in str(self.settings.facilities_csv).lower()
        self.events: list[dict] = []  # anonymised counters for the MoH insight dashboard (phase 2)

    @classmethod
    def from_settings(cls, settings: Optional[Settings] = None) -> "Router":
        settings = settings or get_settings()
        return cls(
            retriever=Retriever.from_dir(settings.content_dir),
            finder=FacilityFinder.from_csv(settings.facilities_csv),
            provider=get_provider(settings.llm_provider, settings.llm_model, settings.llm_timeout),
            settings=settings,
        )

    # ------------------------------------------------------------------
    def handle(self, phone: str, text: str) -> Reply:
        reply = self._route(phone, text or "")
        reply.text = fit_sms(reply.text, self.settings.max_reply_chars)
        self.events.append(
            {
                "user": hash_phone(phone, self.settings.phone_hash_salt),
                "category": reply.category,
                "rule_id": reply.rule_id,
                "content_ids": list(reply.content_ids),
                "ts": int(time.time()),
            }
        )
        return reply

    def _route(self, phone: str, text: str) -> Reply:
        key = hash_phone(phone, self.settings.phone_hash_salt)
        norm = normalise(text)

        # 1. Safety first, always, including mid-conversation.
        flag = red_flags.screen(text)
        if flag:
            self.sessions.clear(key)
            return Reply(text=flag.message, category=flag.category, rule_id=flag.rule_id)

        # 2. Commands
        if norm in _STOP:
            self.sessions.clear(key)
            return Reply(text=STOPPED, category="stop")
        if not norm or norm in _HELP:
            self.sessions.clear(key)
            return Reply(text=WELCOME, category="menu")

        # 3. Facility finder
        pending = self.sessions.get(key) == "awaiting_location"
        is_facility = bool(_FACILITY_KEYWORD.match(norm)) or (
            bool(_FACILITY_WORD.search(norm)) and bool(_NEAR_WORD.search(norm))
        )
        if not (pending or is_facility) and (_LOCATION_STATEMENT.search(norm) or len(norm.split()) <= 3):
            # "Makole" or "naishi kijiji cha Bihawana" sent without KITUO:
            # treat as a facility request only on an exact (non-fuzzy) place match.
            match = self.finder.find(text)
            if match and not match.matched_on.endswith("~"):
                return Reply(
                    text=format_facility_reply(match, self.sample_facility_data),
                    category="facility",
                    content_ids=[match.facility.hfr_code],
                )
        if pending or is_facility:
            match = self.finder.find(text)
            if match:
                self.sessions.clear(key)
                return Reply(
                    text=format_facility_reply(match, self.sample_facility_data),
                    category="facility",
                    content_ids=[match.facility.hfr_code],
                )
            if is_facility and not pending and not extract_place(norm):
                self.sessions.set(key, "awaiting_location")
                return Reply(text=ASK_LOCATION, category="facility")
            self.sessions.clear(key)
            if is_facility or len(norm.split()) <= 3:
                return Reply(text=FACILITY_NOT_FOUND, category="facility")
            # A pending user who asks a real question instead falls through to Q&A.

        # 4. Grounded answer
        hits = self.retriever.search(text, k=3)
        if not hits or hits[0].score < self.settings.min_retrieval_score:
            return Reply(
                text=FALLBACK,
                category="fallback",
                retrieval_score=hits[0].score if hits else 0.0,
            )
        passages = [h.entry for h in hits if h.score >= self.settings.min_retrieval_score]
        answer = grounded_answer(self.provider, text, passages, self.settings.max_reply_chars)
        return Reply(
            text=answer.text,
            category="answer",
            content_ids=[p.id for p in passages],
            source=answer.source,
            retrieval_score=hits[0].score,
        )
