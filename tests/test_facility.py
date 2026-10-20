from nuru.facility import extract_place, format_facility_reply


def test_exact_ward(finder):
    match = finder.find("Makole")
    assert match is not None
    assert match.matched_on == "ward"
    assert match.facility.ward == "Makole"


def test_first_level_of_care_preferred(finder):
    # Makole has a dispensary and a health centre; the dispensary is nearest to the community.
    assert finder.find("makole").facility.facility_type == "dispensary"


def test_keyword_and_filler_words_are_stripped(finder):
    assert extract_place("KITUO kata ya Makole") == "makole"
    assert finder.find("KITUO kata ya Makole").facility.ward == "Makole"
    assert finder.find("naishi kijiji cha Bihawana").facility.ward == "Mbabala"


def test_village_match(finder):
    match = finder.find("Ipagala Juu")
    assert match.matched_on == "village"
    assert match.facility.ward == "Ipagala"


def test_multi_word_ward_with_filler_inside(finder):
    assert finder.find("kiwanja cha ndege").facility.ward == "Kiwanja cha Ndege"


def test_apostrophe_insensitive(finder):
    assert finder.find("changombe").facility.ward == "Chang'ombe"


def test_fuzzy_typo(finder):
    match = finder.find("Ipagla")
    assert match is not None
    assert match.matched_on.endswith("~")
    assert match.facility.ward == "Ipagala"


def test_unknown_place(finder):
    assert finder.find("Atlantis") is None


def test_government_only(finder):
    assert all(f.ownership == "government" for f in finder.facilities)
    assert finder.find("Uhuru").facility.ownership == "government"


def test_reply_labels_sample_data(finder):
    reply = format_facility_reply(finder.find("Makole"), sample_data=True)
    assert "mfano" in reply and "Makole" in reply


def test_router_two_step_flow(router):
    phone = "+255700000010"
    first = router.handle(phone, "KITUO")
    assert first.category == "facility"
    assert "kata" in first.text.lower()
    second = router.handle(phone, "Nkuhungu")
    assert second.category == "facility"
    assert "Nkuhungu" in second.text


def test_router_one_step_and_natural_language(router):
    assert "Kizota" in router.handle("+255700000011", "KITUO Kizota").text
    assert router.handle("+255700000012", "kituo cha afya kilicho karibu Mkonze").category == "facility"
    assert router.handle("+255700000013", "nipo kijiji cha bihawana").category == "facility"


def test_router_place_not_found(router):
    reply = router.handle("+255700000014", "KITUO Atlantis")
    assert reply.category == "facility"
    assert "hatukupata" in reply.text.lower()


def test_location_is_not_stored(router):
    phone = "+255700000015"
    router.handle(phone, "KITUO Makole")
    stored = repr(router.sessions._data) + repr(router.events)
    assert "makole" not in stored.lower()
    assert phone not in stored
