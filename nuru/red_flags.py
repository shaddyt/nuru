"""Red-flag screen. Runs BEFORE retrieval and BEFORE any LLM call.

If any rule matches, NURU replies with a FIXED, clinician-written message and
stops. No AI-generated text is ever sent for a danger sign or a safeguarding
disclosure.

Design choices
--------------
* Rules are deliberately broad. A false positive costs one "go to a facility"
  SMS; a false negative can cost a life. Clinicians tune the rules, not the AI.
* Matching is done on normalised text (see textnorm.normalise), so case,
  punctuation and accents do not matter.
* Messages never repeat what the user wrote, never name a condition, and never
  diagnose. They direct the user to care and offer the facility finder.
* Every fixed message is DRAFT until signed off by the clinical lead. The
  review status is kept next to the text so it can be audited.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .textnorm import normalise

# ---------------------------------------------------------------------------
# Fixed messages (Kiswahili is sent; English is the reviewer reference)
# ---------------------------------------------------------------------------

REVIEW_STATUS = "draft_pending_clinical_review"


@dataclass(frozen=True)
class FixedMessage:
    id: str
    sw: str
    en: str
    review_status: str = REVIEW_STATUS


FIXED_MESSAGES: dict[str, FixedMessage] = {
    m.id: m
    for m in [
        FixedMessage(
            id="URGENT_MATERNAL",
            sw=(
                "NURU: Hii ni dalili ya hatari. Nenda kituo cha afya kilicho karibu SASA HIVI, "
                "usisubiri. Ukishindwa kufika, omba msaada wa usafiri kwa jirani au mhudumu wa "
                "afya wa jamii. Tuma KITUO na jina la kata yako kupata kituo cha karibu."
            ),
            en=(
                "NURU: This is a danger sign. Go to the nearest health facility NOW, do not wait. "
                "If you cannot get there, ask a neighbour or community health worker for transport. "
                "Send KITUO and your ward name to find the nearest facility."
            ),
        ),
        FixedMessage(
            id="URGENT_CHILD",
            sw=(
                "NURU: Mtoto anahitaji kuonwa na mtaalamu wa afya SASA HIVI. Mpeleke kituo cha "
                "afya kilicho karibu bila kuchelewa. Mkinge na baridi njiani na kama anaweza "
                "kunyonya, endelea kumnyonyesha. Tuma KITUO na jina la kata yako."
            ),
            en=(
                "NURU: The child needs to be seen by a health worker NOW. Take the child to the "
                "nearest health facility without delay. Keep the child warm on the way and keep "
                "breastfeeding if the child can feed. Send KITUO and your ward name."
            ),
        ),
        FixedMessage(
            id="URGENT_GENERAL",
            sw=(
                "NURU: Hii ni dalili ya hatari. Nenda kituo cha afya kilicho karibu SASA HIVI au "
                "omba msaada wa haraka. Usisubiri dalili ziishe. Tuma KITUO na jina la kata yako "
                "kupata kituo cha karibu."
            ),
            en=(
                "NURU: This is a danger sign. Go to the nearest health facility NOW or get urgent "
                "help. Do not wait for it to pass. Send KITUO and your ward name to find the "
                "nearest facility."
            ),
        ),
        FixedMessage(
            id="SAFEGUARDING_GBV",
            sw=(
                "NURU: Pole sana, si kosa lako. Nenda kituo cha afya mapema, ndani ya saa 72 kama "
                "inawezekana; kuna dawa za kuzuia VVU na mimba. Ukiwa umeumia, nenda SASA. Msaada "
                "wa bure na wa siri: piga 116. Ukiwa hatarini, nenda mahali salama."
            ),
            en=(
                "NURU: We are so sorry, it is not your fault. Go to a health facility early, within "
                "72 hours if possible; there is medicine to prevent HIV and pregnancy. If you are "
                "hurt, go NOW. Free confidential help: call 116. If you are in danger, go somewhere safe."
            ),
        ),
        FixedMessage(
            id="SAFEGUARDING_SELF_HARM",
            sw=(
                "NURU: Pole, hauko peke yako. Tafadhali mwambie mtu unayemwamini sasa hivi na nenda "
                "kituo cha afya kilicho karibu kupata msaada. Kwa walio chini ya miaka 18, piga 116 "
                "bure. Ukiwa katika hatari sasa, usibaki peke yako."
            ),
            en=(
                "NURU: We are sorry, you are not alone. Please tell someone you trust right now and "
                "go to the nearest health facility for help. If you are under 18, call 116 for free. "
                "If you are in danger now, do not stay alone."
            ),
        ),
    ]
}

# ---------------------------------------------------------------------------
# Vocabulary (regex fragments over normalised text)
# ---------------------------------------------------------------------------

PREGNANCY = (
    r"\bmja ?mzito\b|\bujauzito\b|\bmimba\b|\bpregnan\w*|\bantenatal\b"
)
POSTPARTUM = (
    r"\bnimejifungua\b|\bamejifungua\b|\bkujifungua\b|\bbaada ya kujifungua\b|\bpostpartum\b"
    r"|\bgave birth\b|\bafter (giving )?birth\b|\bafter delivery\b"
)
CHILD = (
    r"\bmtoto\b|\bwatoto\b|\bkichanga\b|\bmchanga\b|\bbaby\b|\bbabies\b|\bchild\b|\binfant\b"
    r"|\bnewborn\b|\bnew born\b|\bmwanangu\b"
)
NEWBORN = (
    r"\bmtoto mchanga\b|\bkichanga\b|\bnewborn\b|\bnew born\b|\bsiku \d+\b|\bwa siku\b"
    r"|\bwiki (moja|mbili|tatu|nne|[1-4])\b|\bdays? old\b|\bweeks? old\b|\bmwezi mmoja\b"
    r"|\bamezaliwa\b|\bjuzi\b.*\bkuzaliwa\b"
)

BLEEDING = r"\bdamu\b|\bbleed\w*|\bblood\b|\bspotting\b"
HEADACHE = r"\bkichwa\b|\bheadache\w*"
SEVERE_HEADACHE = (
    r"kichwa (kinauma|kinaniuma|kinamuuma) sana|maumivu makali ya kichwa|kichwa kikali"
    r"|severe headache|bad headache|terrible headache"
)
VISION = (
    r"\bukungu\b|kuona vibaya|haoni vizuri|sioni vizuri|naona giza|macho (yana|ya)? ?giza"
    r"|nyota nyota|\bblurr\w*|blurred|\bvision\b|seeing (spots|stars)"
)
FEVER = r"\bhoma\b|\bjoto\b|\bfever\w*|\btemperature\b|\bhot body\b"
COLD_BODY = r"\bbaridi sana\b|mwili (wa|una) baridi|\bcold\b"
SWELLING_FACE_HANDS = (
    r"kuvimba uso|uso (umevimba|unavimba)|mikono (imevimba|inavimba)|kuvimba mikono"
    r"|swollen (face|hands)|swelling (of )?(the |my )?(face|hands)"
)
SEVERE_ABDO = (
    r"tumbo\w* .*(sana|makali)|maumivu makali ya tumbo|severe (abdominal|stomach|belly) pain"
)
JAUNDICE = r"\bmanjano\b|\byellow\w*|\bjaundice\b"
# Require the yellow colour to be about the baby (skin, eyes, body), so a question
# about yellow first milk (colostrum) is not escalated.
JAUNDICE_BODY = (
    r"\bngozi\b|\bmacho\b|\bmwili\b|\bviganja\b|\bnyayo\b|\bana manjano\b|amekuwa (wa )?manjano"
    r"|\bskin\b|\beyes?\b|\bbody\b|\bpalms\b|\bsoles\b|\bis yellow\b|turned yellow|looks yellow|\bjaundice\b"
)


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    message_id: str
    any_of: tuple[str, ...] = ()
    all_of: tuple[str, ...] = ()
    context_aware: bool = False  # pick child / maternal / general message from context
    _compiled_any: tuple[re.Pattern, ...] = field(default=(), init=False, repr=False, compare=False)
    _compiled_all: tuple[re.Pattern, ...] = field(default=(), init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled_any", tuple(re.compile(p) for p in self.any_of))
        object.__setattr__(self, "_compiled_all", tuple(re.compile(p) for p in self.all_of))

    def matches(self, text: str) -> bool:
        if self._compiled_any and not any(p.search(text) for p in self._compiled_any):
            return False
        if self._compiled_all and not all(p.search(text) for p in self._compiled_all):
            return False
        return bool(self._compiled_any or self._compiled_all)


# Ordered by priority: the first matching rule wins.
RULES: tuple[Rule, ...] = (
    # Safeguarding: immediate risk to life
    Rule(
        id="self_harm",
        description="Suicidal thoughts or self-harm",
        message_id="SAFEGUARDING_SELF_HARM",
        any_of=(
            r"kujiua|nijiue|najiua|nataka kufa|kujidhuru|nijidhuru|kujitoa uhai"
            r"|kill myself|suicid\w*|end my life|want to die|self harm|hurt myself",
        ),
    ),
    # Medical emergencies
    Rule(
        id="convulsions_unconscious",
        description="Convulsions, fits, fainting or loss of consciousness",
        message_id="URGENT_GENERAL",
        context_aware=True,
        any_of=(
            r"degedege|kifafa|anatetemeka mwili mzima|\bconvuls\w*|\bseizure\w*|\bfitting\b|\bfits\b"
            r"|kupoteza fahamu|amepoteza fahamu|nimepoteza fahamu|hana fahamu|amezimia|nimezimia|kuzimia"
            r"|\bunconscious\b|\bfainted\b|\bfainting\b|passed out",
        ),
    ),
    Rule(
        id="breathing",
        description="Difficulty or fast breathing",
        message_id="URGENT_GENERAL",
        context_aware=True,
        any_of=(
            r"kupumua kwa shida|anapumua kwa shida|napumua kwa shida|anapumua haraka|hapumui"
            r"|shida ya kupumua|kubanwa na pumzi|anabanwa na pumzi|kifua kinabonyea|kushindwa kupumua"
            r"|difficult\w* breathing|difficulty breathing|fast breathing|not breathing|chest indrawing"
            r"|cant breathe|cannot breathe|short of breath",
        ),
    ),
    Rule(
        id="bleeding_pregnancy_postpartum",
        description="Any vaginal bleeding in pregnancy or heavy bleeding after birth",
        message_id="URGENT_MATERNAL",
        all_of=(BLEEDING, f"(?:{PREGNANCY})|(?:{POSTPARTUM})"),
    ),
    Rule(
        id="headache_vision",
        description="Severe headache with blurred vision (possible pre-eclampsia)",
        message_id="URGENT_MATERNAL",
        all_of=(HEADACHE, VISION),
    ),
    Rule(
        id="severe_headache_pregnancy",
        description="Severe headache in pregnancy or after birth",
        message_id="URGENT_MATERNAL",
        all_of=(SEVERE_HEADACHE, f"(?:{PREGNANCY})|(?:{POSTPARTUM})"),
    ),
    Rule(
        id="swelling_pregnancy",
        description="Swelling of face or hands in pregnancy",
        message_id="URGENT_MATERNAL",
        all_of=(SWELLING_FACE_HANDS, f"(?:{PREGNANCY})|(?:{POSTPARTUM})"),
    ),
    Rule(
        id="waters_breaking",
        description="Waters breaking or leaking fluid before labour",
        message_id="URGENT_MATERNAL",
        any_of=(
            r"maji (yanatoka|yamevunjika|yamepasuka|yananitoka)|chupa (imepasuka|imevunjika)"
            r"|kuvunja chupa|chupa kupasuka|waters? (broke|broken|breaking)|leaking fluid",
        ),
    ),
    Rule(
        id="reduced_fetal_movement",
        description="Baby moving less or not moving in the womb",
        message_id="URGENT_MATERNAL",
        any_of=(
            r"mtoto (tumboni )?(hachezi|hacheza|hasogei|ameacha kucheza|anacheza kidogo)"
            r"|baby (is )?(not|stopped|isnt) moving|no fetal movement|reduced (fetal|baby) movement"
            r"|baby moving less",
        ),
    ),
    Rule(
        id="severe_abdominal_pain_pregnancy",
        description="Severe abdominal pain in pregnancy",
        message_id="URGENT_MATERNAL",
        all_of=(SEVERE_ABDO, PREGNANCY),
    ),
    Rule(
        id="fever_pregnancy_postpartum",
        description="Fever in pregnancy or after birth",
        message_id="URGENT_MATERNAL",
        all_of=(FEVER, f"(?:{PREGNANCY})|(?:{POSTPARTUM})"),
    ),
    Rule(
        id="child_cannot_feed",
        description="Baby not breastfeeding or child unable to drink (IMCI general danger sign)",
        message_id="URGENT_CHILD",
        any_of=(
            r"hanyonyi|hawezi kunyonya|ameshindwa kunyonya|anashindwa kunyonya|amekataa kunyonya"
            r"|anakataa kunyonya|haonyonyi|hawezi kunywa|hanywi|anashindwa kunywa|ameshindwa kunywa"
            r"|not (breast ?)?feeding|unable to (drink|feed|breast ?feed)|(cant|cannot|wont) (drink|feed|breast ?feed)"
            r"|refus\w* to (feed|breast ?feed|drink)",
        ),
    ),
    Rule(
        id="child_vomits_everything",
        description="Child vomits everything (IMCI general danger sign)",
        message_id="URGENT_CHILD",
        any_of=(r"anatapika kila kitu|kutapika kila kitu|anatapika kila anachokula|vomit\w* everything",),
    ),
    Rule(
        id="child_lethargic",
        description="Child lethargic or floppy (IMCI general danger sign)",
        message_id="URGENT_CHILD",
        any_of=(r"amelegea|hana nguvu kabisa|hachangamki|\blethargic\b|\bfloppy\b|very sleepy and hard to wake",),
    ),
    Rule(
        id="newborn_fever_or_cold",
        description="Fever or cold body in a newborn",
        message_id="URGENT_CHILD",
        all_of=(f"(?:{FEVER})|(?:{COLD_BODY})", NEWBORN),
    ),
    Rule(
        id="newborn_jaundice",
        description="Yellow skin or eyes in a newborn",
        message_id="URGENT_CHILD",
        all_of=(JAUNDICE, NEWBORN, JAUNDICE_BODY),
    ),
    # Safeguarding: violence and abuse disclosures
    Rule(
        id="gbv_disclosure",
        description="Sexual violence, intimate partner violence or abuse",
        message_id="SAFEGUARDING_GBV",
        any_of=(
            r"nimebakwa|amenibaka|alinibaka|wamenibaka|walinibaka|kubakwa|ubakaji|amebakwa"
            r"|amenilazimisha|alinilazimisha|kulazimishwa (kufanya )?ngono"
            r"|ananipiga|amenipiga|alinipiga|wananipiga|kupigwa na mume|ananinyanyasa|unyanyasaji|ukatili"
            r"|\braped?\b|sexual(ly)? assault\w*|forced me|beats me|hit me|\babus\w*",
        ),
    ),
)

_CATEGORY = {
    "URGENT_MATERNAL": "red_flag",
    "URGENT_CHILD": "red_flag",
    "URGENT_GENERAL": "red_flag",
    "SAFEGUARDING_GBV": "safeguarding",
    "SAFEGUARDING_SELF_HARM": "safeguarding",
}

_CHILD_RE = re.compile(CHILD)
_MATERNAL_RE = re.compile(f"(?:{PREGNANCY})|(?:{POSTPARTUM})")


@dataclass(frozen=True)
class RedFlagResult:
    rule_id: str
    category: str  # "red_flag" or "safeguarding"
    message_id: str
    message: str


def _resolve_message_id(rule: Rule, text: str) -> str:
    if not rule.context_aware:
        return rule.message_id
    if _CHILD_RE.search(text):
        return "URGENT_CHILD"
    if _MATERNAL_RE.search(text):
        return "URGENT_MATERNAL"
    return rule.message_id


def screen(text: str) -> Optional[RedFlagResult]:
    """Return a RedFlagResult if any danger sign or safeguarding rule matches."""
    norm = normalise(text)
    if not norm:
        return None
    for rule in RULES:
        if rule.matches(norm):
            message_id = _resolve_message_id(rule, norm)
            return RedFlagResult(
                rule_id=rule.id,
                category=_CATEGORY[message_id],
                message_id=message_id,
                message=FIXED_MESSAGES[message_id].sw,
            )
    return None
