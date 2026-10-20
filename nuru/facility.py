"""Facility finder: user texts her ward (kata) or village (kijiji), NURU replies
with the nearest government facility.

Location is ASKED, never tracked: NURU does not use cell-tower or GPS data and
does not store the place a user typed.

The data file must be the official Ministry of Health Health Facility
Registry (HFR) export. The file shipped in data/ is a small illustrative
SAMPLE for demos only.

Matching order: exact ward, exact village, then a typo-tolerant fuzzy match
(difflib) on ward and village names. Within a matched area, facilities are
ranked by level of care suited to a first visit: dispensary and health centre
first (closest to the community), then hospitals.
"""

from __future__ import annotations

import csv
import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .textnorm import normalise

TYPE_LABEL_SW = {
    "dispensary": "Zahanati",
    "health_centre": "Kituo cha Afya",
    "district_hospital": "Hospitali ya Wilaya",
    "regional_referral_hospital": "Hospitali ya Rufaa ya Mkoa",
    "hospital": "Hospitali",
}
TYPE_RANK = {"dispensary": 0, "health_centre": 1, "hospital": 2, "district_hospital": 2, "regional_referral_hospital": 3}

# Words users put around a place name: "KITUO Makole", "kata ya Makole", "naishi kijiji cha Mbabala"
_LOCATION_NOISE = re.compile(
    r"\b(kituo|vituo|hospitali|zahanati|clinic|kliniki|facility|health|centre|center|karibu|nearest|near"
    r"|kata|ward|kijiji|village|mtaa|cha|ya|la|wa|ni|naishi|nipo|niko|mimi|i|live|in|at|my|is|the|of"
    r"|nataka|natafuta|nipe|tafadhali|find|where|wapi|kipi|kipo|gani|afya|kilicho|iliyo|hospital|closest"
    r"|nearby|me|to|go|niende|nenda)\b"
)


@dataclass(frozen=True)
class Facility:
    hfr_code: str
    name: str
    facility_type: str
    ownership: str
    region: str
    council: str
    ward: str
    villages: tuple[str, ...]

    @property
    def type_label(self) -> str:
        return TYPE_LABEL_SW.get(self.facility_type, self.facility_type.replace("_", " ").title())


@dataclass(frozen=True)
class FacilityMatch:
    facility: Facility
    matched_on: str  # "ward", "village", "ward~", "village~" (~ = fuzzy)
    place: str


def load_facilities(path: Path) -> list[Facility]:
    with open(path, encoding="utf-8") as fh:
        rows = (line for line in fh if line.strip() and not line.lstrip().startswith("#"))
        reader = csv.DictReader(rows)
        out = []
        for r in reader:
            out.append(
                Facility(
                    hfr_code=r["hfr_code"].strip(),
                    name=r["name"].strip(),
                    facility_type=r["facility_type"].strip(),
                    ownership=r["ownership"].strip(),
                    region=r["region"].strip(),
                    council=r["council"].strip(),
                    ward=r["ward"].strip(),
                    villages=tuple(v.strip() for v in r.get("villages", "").split(";") if v.strip()),
                )
            )
    return out


def extract_place(text: str) -> str:
    """Strip filler words so "KITUO kata ya Makole" becomes "makole"."""
    return re.sub(r"\s+", " ", _LOCATION_NOISE.sub(" ", normalise(text))).strip()


class FacilityFinder:
    def __init__(self, facilities: list[Facility], government_only: bool = True):
        if government_only:
            facilities = [f for f in facilities if f.ownership.lower() in {"government", "public", "serikali"}]
        self.facilities = facilities
        self.by_ward: dict[str, list[Facility]] = {}
        self.by_village: dict[str, list[Facility]] = {}
        for f in facilities:
            # Index keys go through the same filler-word stripping as user input,
            # so "Kiwanja cha Ndege" and "kata ya kiwanja cha ndege" meet in the middle.
            self.by_ward.setdefault(extract_place(f.ward), []).append(f)
            for v in f.villages:
                self.by_village.setdefault(extract_place(v), []).append(f)

    @classmethod
    def from_csv(cls, path: Path) -> "FacilityFinder":
        return cls(load_facilities(path))

    @staticmethod
    def _best(candidates: list[Facility]) -> Facility:
        return sorted(candidates, key=lambda f: (TYPE_RANK.get(f.facility_type, 9), f.name))[0]

    def find(self, text: str) -> Optional[FacilityMatch]:
        place = extract_place(text)
        if not place:
            return None
        if place in self.by_ward:
            return FacilityMatch(self._best(self.by_ward[place]), "ward", place)
        if place in self.by_village:
            return FacilityMatch(self._best(self.by_village[place]), "village", place)

        ward_hit = difflib.get_close_matches(place, list(self.by_ward), n=1, cutoff=0.8)
        if ward_hit:
            return FacilityMatch(self._best(self.by_ward[ward_hit[0]]), "ward~", ward_hit[0])
        village_hit = difflib.get_close_matches(place, list(self.by_village), n=1, cutoff=0.8)
        if village_hit:
            return FacilityMatch(self._best(self.by_village[village_hit[0]]), "village~", village_hit[0])

        # Multi-word messages such as "makole dodoma": try each word on its own
        for token in place.split():
            if token in self.by_ward:
                return FacilityMatch(self._best(self.by_ward[token]), "ward", token)
            if token in self.by_village:
                return FacilityMatch(self._best(self.by_village[token]), "village", token)
        return None


def format_facility_reply(match: FacilityMatch, sample_data: bool = True) -> str:
    f = match.facility
    label = "" if f.type_label.lower() in f.name.lower() else f" ({f.type_label})"
    msg = f"NURU: Kituo cha serikali kilicho karibu: {f.name}{label}, kata ya {f.ward}, {f.council}."
    if match.matched_on.endswith("~"):
        msg += f" Tumetafuta kwa jina: {match.place.title()}. Kama si sahihi, tuma KITUO na jina sahihi."
    if sample_data:
        msg += " [Data ya mfano, si rasmi]"
    return msg
