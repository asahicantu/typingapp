from typingapp.engine.keyboard_map import finger_for_char


def test_left_pinky_keys():
    for ch in ("q", "a", "z", "1"):
        assert finger_for_char(ch) == ("Left", "pinky")


def test_left_ring_keys():
    for ch in ("w", "s", "x", "2"):
        assert finger_for_char(ch) == ("Left", "ring")


def test_left_middle_keys():
    for ch in ("e", "d", "c", "3"):
        assert finger_for_char(ch) == ("Left", "middle")


def test_left_index_keys_including_reach_column():
    # standard touch-typing charts give the index finger both its home column
    # and the adjacent reach column (f/r/v/g/t/b on the left hand)
    for ch in ("f", "r", "v", "g", "t", "b", "4", "5"):
        assert finger_for_char(ch) == ("Left", "index")


def test_right_index_keys_including_reach_column():
    for ch in ("j", "u", "m", "h", "y", "n", "6", "7"):
        assert finger_for_char(ch) == ("Right", "index")


def test_right_middle_keys():
    for ch in ("k", "i", ",", "8"):
        assert finger_for_char(ch) == ("Right", "middle")


def test_right_ring_keys():
    for ch in ("l", "o", ".", "9"):
        assert finger_for_char(ch) == ("Right", "ring")


def test_right_pinky_keys():
    for ch in ("p", ";", "/", "0", "'", "[", "]", "-", "="):
        assert finger_for_char(ch) == ("Right", "pinky")


def test_space_uses_thumb():
    result = finger_for_char(" ")
    assert result is not None
    assert result[1] == "thumb"


def test_uppercase_letters_map_to_same_finger_as_lowercase():
    assert finger_for_char("Q") == finger_for_char("q")
    assert finger_for_char("A") == finger_for_char("a")


def test_unmapped_character_returns_none():
    assert finger_for_char("€") is None
    assert finger_for_char("\n") is None


def test_newline_and_tab_return_none_not_crash():
    assert finger_for_char("\t") is None
