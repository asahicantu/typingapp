from __future__ import annotations
import array
import math
import struct
import sys

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


class SoundPlayer:
    """Plays short key-click / error tones. Never raises — disables itself
    silently if no audio backend is available (e.g. non-Windows or a
    headless environment)."""

    def __init__(self) -> None:
        self._enabled = False
        self._winsound = None
        self._click: bytes | None = None
        self._error: bytes | None = None
        if sys.platform != "win32":
            return
        try:
            import winsound
            self._winsound = winsound
            self._click = _tone_wav(880.0, 0.03)
            self._error = _tone_wav(220.0, 0.08)
            self._enabled = True
        except Exception:
            self._enabled = False

    def play_correct(self) -> None:
        self._play(self._click)

    def play_error(self) -> None:
        self._play(self._error)

    def _play(self, wav_bytes: bytes | None) -> None:
        if not self._enabled or wav_bytes is None:
            return
        try:
            self._winsound.PlaySound(
                wav_bytes,
                self._winsound.SND_MEMORY | self._winsound.SND_ASYNC,
            )
        except Exception:
            self._enabled = False
