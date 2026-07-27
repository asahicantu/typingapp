from __future__ import annotations

# Standard US-QWERTY touch-typing finger assignments. Each entry maps a
# lowercase key to (hand, finger); shifted/uppercase variants and digit-row
# punctuation share the same finger as their unshifted key on a real keyboard,
# handled by normalizing the input character before lookup.
_KEY_TO_FINGER: dict[str, tuple[str, str]] = {
    # number row
    "1": ("Left", "pinky"), "2": ("Left", "ring"), "3": ("Left", "middle"),
    "4": ("Left", "index"), "5": ("Left", "index"),
    "6": ("Right", "index"), "7": ("Right", "index"),
    "8": ("Right", "middle"), "9": ("Right", "ring"), "0": ("Right", "pinky"),
    "-": ("Right", "pinky"), "=": ("Right", "pinky"),
    # top row
    "q": ("Left", "pinky"), "w": ("Left", "ring"), "e": ("Left", "middle"),
    "r": ("Left", "index"), "t": ("Left", "index"),
    "y": ("Right", "index"), "u": ("Right", "index"),
    "i": ("Right", "middle"), "o": ("Right", "ring"), "p": ("Right", "pinky"),
    "[": ("Right", "pinky"), "]": ("Right", "pinky"),
    # home row
    "a": ("Left", "pinky"), "s": ("Left", "ring"), "d": ("Left", "middle"),
    "f": ("Left", "index"), "g": ("Left", "index"),
    "h": ("Right", "index"), "j": ("Right", "index"),
    "k": ("Right", "middle"), "l": ("Right", "ring"), ";": ("Right", "pinky"),
    "'": ("Right", "pinky"),
    # bottom row
    "z": ("Left", "pinky"), "x": ("Left", "ring"), "c": ("Left", "middle"),
    "v": ("Left", "index"), "b": ("Left", "index"),
    "n": ("Right", "index"), "m": ("Right", "index"),
    ",": ("Right", "middle"), ".": ("Right", "ring"), "/": ("Right", "pinky"),
    # space
    " ": ("Left", "thumb"),
}


def finger_for_char(char: str) -> tuple[str, str] | None:
    """Return (hand, finger) for the given character on a standard US-QWERTY
    touch-typing layout, or None if the character has no defined home. Case-
    insensitive: uppercase letters map to the same finger as their lowercase
    form (a real keyboard's Shift key is a separate finger concern this app
    doesn't model)."""
    if len(char) != 1:
        return None
    return _KEY_TO_FINGER.get(char.lower())
