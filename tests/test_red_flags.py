"""Red flags must be caught, must use fixed text, and must always win over the AI."""

import pytest

from nuru import red_flags
from nuru.red_flags import FIXED_MESSAGES, screen

MATERNAL = [
    "Nina mimba ya miezi 6 natoka damu",
    "NIMEJIFUNGUA juzi na natoka damu nyingi sana",
    "mjamzito anatoka damu ukeni",
    "I am pregnant and bleeding",
    "kichwa kinauma sana na naona ukungu",
    "Nina ujauzito, kichwa kinaniuma sana",
    "maji yamevunjika lakini uchungu bado",
    "mtoto tumboni hachezi tangu jana",
    "mjamzito ana homa kali",
    "nina mimba uso umevimba",
    "Nina mimba na maumivu makali ya tumbo",
    "mke wangu ni mjamzito ana degedege",
]
CHILD = [
    "mtoto wangu mchanga hanyonyi",
    "Mtoto hawezi kunywa wala kunyonya",
    "my baby is not breastfeeding",
    "mtoto mchanga wa siku 5 ana homa",
    "newborn has a fever",
    "mtoto ana degedege",
    "mtoto wangu anapumua kwa shida",
    "mtoto anatapika kila kitu",
    "mtoto mchanga ana manjano machoni",
    "mtoto amelegea hachangamki",
]
GENERAL = ["amepoteza fahamu", "nimezimia mara mbili leo"]
SAFEGUARDING = [
    ("nimebakwa jana usiku", "SAFEGUARDING_GBV"),
    ("mume wangu ananipiga kila siku", "SAFEGUARDING_GBV"),
    ("I was raped", "SAFEGUARDING_GBV"),
    ("nataka kujiua", "SAFEGUARDING_SELF_HARM"),
    ("I want to kill myself", "SAFEGUARDING_SELF_HARM"),
]
SAFE = [
    "hedhi ya kawaida ni siku ngapi",
    "ni kweli uzazi wa mpango unaleta utasa",
    "kondomu inazuia ukimwi",
    "mama mjamzito ale nini",
    "nianze kliniki ya ujauzito lini",
    "maziwa ya kwanza ya manjano ni machafu",
    "dalili za hatari wakati wa ujauzito ni zipi",
    "mtoto apate chanjo lini",
]


@pytest.mark.parametrize("text", MATERNAL)
def test_maternal_danger_signs(text):
    result = screen(text)
    assert result is not None, text
    assert result.category == "red_flag"
    assert result.message_id == "URGENT_MATERNAL"


@pytest.mark.parametrize("text", CHILD)
def test_child_danger_signs(text):
    result = screen(text)
    assert result is not None, text
    assert result.message_id == "URGENT_CHILD"


@pytest.mark.parametrize("text", GENERAL)
def test_general_danger_signs(text):
    result = screen(text)
    assert result is not None, text
    assert result.category == "red_flag"


@pytest.mark.parametrize("text,message_id", SAFEGUARDING)
def test_safeguarding(text, message_id):
    result = screen(text)
    assert result is not None, text
    assert result.category == "safeguarding"
    assert result.message_id == message_id


@pytest.mark.parametrize("text", SAFE)
def test_non_urgent_questions_are_not_flagged(text):
    assert screen(text) is None, text


def test_screen_is_case_and_punctuation_insensitive():
    assert screen("NINA MIMBA!!! NATOKA DAMU...") is not None


def test_fixed_messages_are_verbatim_and_never_echo_input():
    text = "Nina mimba ya miezi 6 natoka damu, jina langu ni Asha"
    result = screen(text)
    assert result.message == FIXED_MESSAGES["URGENT_MATERNAL"].sw
    assert "Asha" not in result.message
    assert "damu" not in result.message.lower()


def test_every_fixed_message_points_to_care_and_is_marked_draft():
    for msg in FIXED_MESSAGES.values():
        assert "kituo cha afya" in msg.sw.lower()
        assert msg.review_status == "draft_pending_clinical_review"


def test_every_rule_points_to_a_known_message():
    for rule in red_flags.RULES:
        assert rule.message_id in FIXED_MESSAGES


class ExplodingProvider:
    """An LLM that must never be called for a red flag."""

    name = "exploding"

    def generate(self, question, passages, max_chars):  # pragma: no cover - must not run
        raise AssertionError("LLM was called for a red-flag message")


class OverconfidentProvider:
    name = "overconfident"

    def generate(self, question, passages, max_chars):  # pragma: no cover - must not run
        return "Usijali, ni kawaida. Pumzika nyumbani."


@pytest.mark.parametrize("text", MATERNAL + CHILD + [t for t, _ in SAFEGUARDING])
def test_red_flag_wins_over_ai(router, text):
    router.provider = ExplodingProvider()
    reply = router.handle("+255700000001", text)
    assert reply.category in {"red_flag", "safeguarding"}
    assert reply.source is None
    assert reply.text in {m.sw for m in FIXED_MESSAGES.values()}


def test_red_flag_wins_even_when_question_matches_content(router):
    # This message matches library content about antenatal care AND contains a danger sign.
    router.provider = OverconfidentProvider()
    reply = router.handle("+255700000002", "nianze kliniki ya ujauzito lini? natoka damu")
    assert reply.category == "red_flag"
    assert "Usijali" not in reply.text


def test_red_flag_wins_during_facility_conversation(router):
    phone = "+255700000003"
    assert router.handle(phone, "KITUO").category == "facility"
    reply = router.handle(phone, "nina mimba natoka damu")
    assert reply.category == "red_flag"


def test_ai_is_used_for_normal_questions(router):
    calls = []

    class FakeProvider:
        name = "fake"

        def generate(self, question, passages, max_chars):
            calls.append(question)
            return "Jibu la majaribio."

    router.provider = FakeProvider()
    reply = router.handle("+255700000004", "kondomu inazuia ukimwi")
    assert calls, "provider should be called for a normal question"
    assert reply.source == "llm:fake"
    assert reply.text == "Jibu la majaribio."
