from typingapp.engine.keyboard_sanitize import sanitize_for_keyboard


def test_ascii_text_passes_through_unchanged():
    text = "The quick brown fox jumps over the lazy dog. 123!"
    assert sanitize_for_keyboard(text) == text


def test_curly_double_quotes_become_straight_quotes():
    assert sanitize_for_keyboard("“Hello”") == '"Hello"'


def test_curly_single_quotes_and_apostrophe_become_straight_apostrophe():
    assert sanitize_for_keyboard("‘Hello’") == "'Hello'"
    assert sanitize_for_keyboard("don’t") == "don't"


def test_em_dash_and_en_dash_become_hyphen():
    assert sanitize_for_keyboard("wait—no") == "wait-no"
    assert sanitize_for_keyboard("pages 1–2") == "pages 1-2"


def test_ellipsis_character_becomes_a_single_period():
    # NOTE: the single-character ellipsis (U+2026) must become exactly ONE
    # ASCII character, not "...", to preserve 1:1 character-offset correspondence
    # with the original book text (see Global Constraints).
    assert sanitize_for_keyboard("wait…") == "wait."


def test_non_breaking_space_becomes_a_regular_space():
    assert sanitize_for_keyboard("100 km") == "100 km"


def test_unmappable_character_becomes_a_single_space():
    # e.g. a CJK character or emoji has no sane single-key ASCII equivalent
    assert sanitize_for_keyboard("hello中 world") == "hello  world"


def test_output_length_always_equals_input_length():
    # the invariant every other book-offset computation in this codebase depends on
    samples = [
        "plain ascii",
        "“curly quotes’ and — dashes… mixed in中text",
        "",
    ]
    for text in samples:
        assert len(sanitize_for_keyboard(text)) == len(text)


def test_unknown_layout_falls_back_to_en_us_qwerty_behavior():
    text = "“Hello”"
    assert sanitize_for_keyboard(text, layout="klingon") == sanitize_for_keyboard(text, layout="en-us-qwerty")
