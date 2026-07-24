from __future__ import annotations
import array
import atexit
import math
import os
import struct
import sys
import tempfile

SAMPLE_RATE = 44100


def _tone_wav(freq: float, duration: float, volume: float = 0.35) -> bytes:
    n_samples = int(SAMPLE_RATE * duration)
    amplitude = int(32767 * volume)
    samples = array.array("h", [
        int(amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        for i in range(n_samples)
    ])
    data = samples.tobytes()
    byte_rate = SAMPLE_RATE * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(data), b"WAVE",
        b"fmt ", 16, 1, 1, SAMPLE_RATE, byte_rate, 2, 16,
        b"data", len(data),
    )
    return header + data


def _write_temp_wav(wav_bytes: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="typingapp_")
    with os.fdopen(fd, "wb") as f:
        f.write(wav_bytes)
    return path


class SoundPlayer:
    """Plays short key-click / error tones. Never raises — disables itself
    silently if no audio backend is available (e.g. non-Windows or a
    headless environment).

    winsound.PlaySound refuses to combine SND_MEMORY with SND_ASYNC (raises
    RuntimeError), so async playback requires a real file on disk. The two
    tones are rendered once at startup into temp WAV files and played from
    there for the lifetime of the process.
    """

    def __init__(self) -> None:
        self._enabled = False
        self._winsound = None
        self._click_path: str | None = None
        self._error_path: str | None = None
        if sys.platform != "win32":
            return
        try:
            import winsound
            self._winsound = winsound
            self._click_path = _write_temp_wav(_tone_wav(880.0, 0.03))
            self._error_path = _write_temp_wav(_tone_wav(220.0, 0.08))
            atexit.register(self._cleanup)
            self._enabled = True
        except Exception:
            self._enabled = False

    def play_correct(self) -> None:
        self._play(self._click_path)

    def play_error(self) -> None:
        self._play(self._error_path)

    def _play(self, path: str | None) -> None:
        if not self._enabled or path is None:
            return
        try:
            self._winsound.PlaySound(
                path,
                self._winsound.SND_FILENAME | self._winsound.SND_ASYNC,
            )
        except Exception:
            self._enabled = False

    def _cleanup(self) -> None:
        for path in (self._click_path, self._error_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
