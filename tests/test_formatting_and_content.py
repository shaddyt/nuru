"""Reply length, GSM-7 safety and content library integrity."""

import pytest

from nuru.formatting import fit_sms, is_gsm7, segment_count, septet_length, to_gsm7
from nuru.red_flags import FIXED_MESSAGES
from nuru.router import ASK_LOCATION, FACILITY_NOT_FOUND, FALLBACK, STOPPED, WELCOME

MAX = 306  # 2 concatenated GSM-7 segments of 153


def test_segment_maths():
    assert segment_count("a" * 160) == 1
    assert segment_count("a" * 161) == 2
    assert segment_count("a" * 306) == 2
    assert segment_count("a" * 307) == 3
    assert septet_length("[]") == 4


def test_transliteration_removes_unicode():
    raw = "\u201cHabari\u201d \u2014 ni\u2019 sawa\u2026 \U0001F600"
    out = to_gsm7(raw)
    assert is_gsm7(out)
    assert "\u2014" not in out


def test_fit_sms_never_exceeds_limit_and_ends_cleanly():
    long = ("Hii ni sentensi ndefu ya majaribio kuhusu afya. " * 20).strip()
    out = fit_sms(long, MAX)
    assert septet_length(out) <= MAX
    assert segment_count(out) <= 2
    assert out.endswith(".")


def test_fit_sms_does_not_cut_mid_word():
    out = fit_sms("neno " * 100, 50)
    assert septet_length(out) <= 50
    assert not out.rstrip(".").endswith("ne")


@pytest.mark.parametrize("text", [WELCOME, STOPPED, ASK_LOCATION, FACILITY_NOT_FOUND, FALLBACK])
def test_system_messages_fit(text):
    assert is_gsm7(text) and septet_length(text) <= MAX


@pytest.mark.parametrize("msg_id", list(FIXED_MESSAGES))
def test_fixed_red_flag_messages_fit_untruncated(msg_id):
    text = FIXED_MESSAGES[msg_id].sw
    assert is_gsm7(text), msg_id
    assert septet_length(text) <= MAX, (msg_id, septet_length(text))


def test_content_library_size_and_status(retriever):
    entries = retriever.entries
    assert 15 <= len(entries) <= 25
    for e in entries:
        assert e.status == "draft_pending_clinical_review", e.id
        assert e.questions and e.answer_sw and e.note_en and e.sources, e.id


def test_content_answers_fit_two_sms_untruncated(retriever):
    for e in retriever.entries:
        assert is_gsm7(e.answer_sw), e.id
        assert septet_length(e.answer_sw) <= MAX, (e.id, septet_length(e.answer_sw))


def test_content_covers_required_topics(retriever):
    stages = {e.life_stage for e in retriever.entries}
    assert {"adolescence", "preconception", "pregnancy", "postpartum", "newborn"} <= stages
    assert sum(e.type == "myth" for e in retriever.entries) >= 4


@pytest.mark.parametrize(
    "question",
    [
        "Je ni kweli uzazi wa mpango unaleta utasa?",
        "hedhi yangu haiji kwa mpangilio",
        "nianze kliniki ya ujauzito lini",
        "maziwa ya kwanza ni machafu",
        "kondomu inazuia ukimwi",
        "x" * 500,
        "nina swali refu sana " * 40,
    ],
)
def test_every_router_reply_fits(router, question):
    reply = router.handle("+255700000020", question)
    assert is_gsm7(reply.text)
    assert septet_length(reply.text) <= MAX
    assert reply.segments <= 2


def test_long_llm_output_is_trimmed(router):
    class VerboseProvider:
        name = "verbose"

        def generate(self, question, passages, max_chars):
            return "Hili ni jibu refu sana kutoka kwa AI. " * 30

    router.provider = VerboseProvider()
    reply = router.handle("+255700000021", "kondomu inazuia ukimwi")
    assert reply.source == "llm:verbose"
    assert septet_length(reply.text) <= MAX


def test_failing_llm_falls_back_to_library(router):
    class BrokenProvider:
        name = "broken"

        def generate(self, question, passages, max_chars):
            raise TimeoutError("provider down")

    router.provider = BrokenProvider()
    reply = router.handle("+255700000022", "kondomu inazuia ukimwi")
    assert reply.category == "answer"
    assert reply.source == "library"
    assert reply.content_ids[0] == "sti_condoms"


def test_off_topic_gets_safe_fallback(router):
    reply = router.handle("+255700000023", "bei ya mahindi sokoni leo")
    assert reply.category == "fallback"
    assert "kituo" in reply.text.lower()


def test_retrieval_finds_expected_entries(retriever):
    expectations = {
        "ni kweli mjamzito asile mayai": "preg_myth_eggs",
        "folic acid": "precon_folic_acid",
        "nitunze kitovu cha mtoto vipi": "nb_cord_care",
        "naweza kupata vvu kwa mbu": "sti_myth_hiv_transmission",
        "nisubiri muda gani kupata mimba nyingine": "precon_birth_spacing",
    }
    for q, expected in expectations.items():
        assert retriever.search(q, k=1)[0].entry.id == expected, q
