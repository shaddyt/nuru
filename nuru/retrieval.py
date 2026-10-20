"""Dependency-light retrieval over the doctor-reviewed content library.

Kiswahili is agglutinative: "hedhi", "hedhini", "nimeingia hedhi" and
"ninapokuwa kwenye hedhi" share a root wrapped in prefixes and suffixes. Plain
word matching misses most of these, so we score with TF-IDF over character
n-grams taken inside each word (plus whole words), and rank entries by cosine
similarity. Pure Python, no numpy, fast enough for a library of hundreds of
entries.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from .textnorm import normalise

STOPWORDS = {
    # Kiswahili
    "na", "ya", "wa", "za", "la", "cha", "vya", "kwa", "ni", "je", "au", "kama", "hii", "huo",
    "hiyo", "hilo", "yangu", "wangu", "changu", "mimi", "wewe", "yeye", "sisi", "nini", "gani",
    "vipi", "kuna", "sana", "tu", "pia", "lakini", "ili", "katika", "kwenye", "hapo", "sasa",
    "naomba", "tafadhali", "habari", "samahani", "nataka", "kujua", "naweza", "inawezekana",
    # English
    "the", "a", "an", "is", "are", "and", "or", "of", "to", "in", "on", "my", "i", "it", "can",
    "what", "how", "do", "does", "be", "for", "with", "please", "should", "when", "about",
}

NGRAM_SIZES = (3, 4, 5)


def _features(text: str) -> Counter:
    feats: Counter = Counter()
    for word in normalise(text).split():
        if word in STOPWORDS or len(word) < 2:
            continue
        feats[f"w:{word}"] += 2  # whole-word match counts more than a fragment
        padded = f"<{word}>"
        for n in NGRAM_SIZES:
            for i in range(len(padded) - n + 1):
                feats[padded[i : i + n]] += 1
    return feats


@dataclass
class ContentEntry:
    id: str
    topic: str
    life_stage: str
    type: str
    questions: list[str]
    keywords: list[str]
    answer_sw: str
    note_en: str = ""
    sources: list[str] = field(default_factory=list)
    status: str = "draft_pending_clinical_review"
    reviewed_by: str | None = None

    def index_text(self) -> str:
        return " ".join(self.questions + self.keywords + [self.topic.replace("_", " ")])


@dataclass
class SearchHit:
    entry: ContentEntry
    score: float


def load_library(content_dir: Path) -> list[ContentEntry]:
    entries: list[ContentEntry] = []
    for path in sorted(Path(content_dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for raw in data.get("entries", []):
            entries.append(
                ContentEntry(
                    id=raw["id"],
                    topic=raw.get("topic", ""),
                    life_stage=raw.get("life_stage", ""),
                    type=raw.get("type", "faq"),
                    questions=list(raw.get("questions", [])),
                    keywords=list(raw.get("keywords", [])),
                    answer_sw=raw["answer_sw"].strip(),
                    note_en=(raw.get("note_en") or "").strip(),
                    sources=list(raw.get("sources", [])),
                    status=raw.get("status", "draft_pending_clinical_review"),
                    reviewed_by=raw.get("reviewed_by"),
                )
            )
    ids = [e.id for e in entries]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"Duplicate content ids: {sorted(duplicates)}")
    return entries


class Retriever:
    def __init__(self, entries: Iterable[ContentEntry]):
        self.entries = list(entries)
        docs = [_features(e.index_text()) for e in self.entries]
        n_docs = len(docs) or 1
        df: Counter = Counter()
        for d in docs:
            df.update(d.keys())
        self.idf = {t: math.log((1 + n_docs) / (1 + c)) + 1.0 for t, c in df.items()}
        # Unseen query terms still count towards the query norm, so a long
        # question with only one matching fragment does not score highly.
        self.unseen_idf = math.log(1 + n_docs) + 1.0
        self.vectors = [self._weigh(d) for d in docs]

    def _weigh(self, feats: Counter) -> dict[str, float]:
        vec = {t: (1 + math.log(c)) * self.idf.get(t, self.unseen_idf) for t, c in feats.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query: str, k: int = 3) -> list[SearchHit]:
        q = self._weigh(_features(query))
        if not q:
            return []
        scored = []
        for entry, vec in zip(self.entries, self.vectors):
            score = sum(w * vec.get(t, 0.0) for t, w in q.items())
            if score > 0:
                scored.append(SearchHit(entry=entry, score=round(score, 4)))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]

    @classmethod
    def from_dir(cls, content_dir: Path) -> "Retriever":
        return cls(load_library(content_dir))
