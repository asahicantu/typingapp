import os
from typingapp.engine.sound import SoundPlayer, _tone_wav


def test_tone_wav_has_riff_header():
    wav_bytes = _tone_wav(440.0, 0.05)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


def test_sound_player_writes_temp_files_when_enabled():
    player = SoundPlayer()
    if player._enabled:
        assert player._click_path and os.path.exists(player._click_path)
        assert player._error_path and os.path.exists(player._error_path)


def test_sound_player_never_raises_on_rapid_play():
    player = SoundPlayer()
    for _ in range(20):
        player.play_correct()
        player.play_error()


def test_sound_player_disabled_is_noop():
    player = SoundPlayer()
    player._enabled = False
    player.play_correct()
    player.play_error()
