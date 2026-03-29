# -*- coding: utf-8 -*-
"""
האזנה רציפה עם Voice Activity Detection (WebRTC VAD).

אלגוריתם:
  1. sounddevice.RawInputStream מכניס frames ל-queue ב-callback.
  2. Thread נפרד קורא frames, מזין לwebrtcvad.
  3. Ring-buffer (pre-speech padding) ← עד שמזוהים NUM_VOICED_TO_TRIGGER frames דיבור.
  4. לאחר זיהוי דיבור: צובר frames.
  5. לאחר SILENCE_FRAMES_TO_END frames שקט (או MAX_SPEECH_FRAMES): מוציא chunk שלם.
  6. ה-chunk (bytes של PCM int16) נכנס ל-speech_queue.

שימוש:
    listener = VADListener()
    listener.start()
    while True:
        chunk = listener.get_next_chunk(timeout=5)   # חוסם עד שיש דיבור
        if chunk:
            # ... תמלל את chunk ...
    listener.stop()
"""

import collections
import queue
import threading
import time
from typing import Optional

import sounddevice as sd
import webrtcvad

from config import (
    SAMPLE_RATE,
    VAD_CHUNK_MS,
    VAD_SILENCE_SEC,
    VAD_MAX_SPEECH_SEC,
    VAD_PRE_SPEECH_PAD_MS,
    VAD_AGGRESSIVENESS,
)

# ─── קבועים (נגזרים מ-config) ────────────────────────────────────────────────
_FRAME_SAMPLES: int = SAMPLE_RATE * VAD_CHUNK_MS // 1000      # 480
_FRAME_BYTES: int = _FRAME_SAMPLES * 2                         # int16 = 2 bytes
_PAD_FRAMES: int = VAD_PRE_SPEECH_PAD_MS // VAD_CHUNK_MS       # frames לפני דיבור
_NUM_VOICED_TO_TRIGGER: int = 3                                 # frames לפתיחת chunk
_SILENCE_FRAMES_TO_END: int = int(VAD_SILENCE_SEC * 1000 / VAD_CHUNK_MS)
_MAX_SPEECH_FRAMES: int = int(VAD_MAX_SPEECH_SEC * 1000 / VAD_CHUNK_MS)
_MIN_SPEECH_FRAMES: int = int(500 / VAD_CHUNK_MS)              # 0.5 שניות דיבור מינימום


class VADListener:
    """האזנה רציפה thread-safe עם VAD."""

    def __init__(self) -> None:
        self._vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self._frame_queue: queue.Queue[bytes] = queue.Queue()
        self._speech_queue: queue.Queue[bytes] = queue.Queue()
        self._running = False
        self._stream: Optional[sd.RawInputStream] = None
        self._vad_thread: Optional[threading.Thread] = None
        self._mute_until: float = 0.0

    # ─── ממשק ציבורי ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """פותח את מזרם השמע ומפעיל את thread ה-VAD."""
        self._running = True
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=_FRAME_SAMPLES,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._vad_thread = threading.Thread(
            target=self._vad_worker, daemon=True, name="vad-worker"
        )
        self._vad_thread.start()

    def stop(self) -> None:
        """עוצר האזנה ומנקה משאבים."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def mute(self, duration: float = 3.0) -> None:
        """משתיק העברת אודיו ל-STT למשך duration שניות (למניעת שמיעה עצמית)."""
        self._mute_until = time.monotonic() + duration

    def get_next_chunk(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        מחכה ל-chunk שמע הבא שזוהה כדיבור.
        מחזיר bytes (PCM int16, 16 kHz, mono) או None אם timeout עבר.
        """
        try:
            return self._speech_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ─── פנימי ────────────────────────────────────────────────────────────────

    def _audio_callback(
        self,
        indata: bytes,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        """נקרא על-ידי sounddevice בכל frame. זורק ל-queue ומיד חוזר."""
        self._frame_queue.put(bytes(indata))

    def _vad_worker(self) -> None:
        """Thread: קורא frames, מפעיל VAD, מוציא chunks שלמים."""
        ring: collections.deque = collections.deque(maxlen=_PAD_FRAMES)
        triggered = False
        voiced_frames: list[bytes] = []
        silent_count = 0
        speech_frame_count = 0

        while self._running:
            try:
                frame = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # webrtcvad דורש בדיוק FRAME_BYTES
            if len(frame) != _FRAME_BYTES:
                continue

            try:
                is_speech = self._vad.is_speech(frame, SAMPLE_RATE)
            except Exception:
                continue

            if not triggered:
                ring.append((frame, is_speech))
                voiced_in_ring = sum(1 for _, s in ring if s)
                if voiced_in_ring >= _NUM_VOICED_TO_TRIGGER:
                    triggered = True
                    voiced_frames = [f for f, _ in ring]
                    speech_frame_count = voiced_in_ring
                    ring.clear()
                    silent_count = 0
            else:
                voiced_frames.append(frame)

                if is_speech:
                    speech_frame_count += 1
                    silent_count = 0
                else:
                    silent_count += 1

                end_by_silence = silent_count > _SILENCE_FRAMES_TO_END
                end_by_max = len(voiced_frames) > _MAX_SPEECH_FRAMES

                if end_by_silence or end_by_max:
                    if (voiced_frames
                            and speech_frame_count >= _MIN_SPEECH_FRAMES
                            and time.monotonic() >= self._mute_until):
                        self._speech_queue.put(b"".join(voiced_frames))
                    triggered = False
                    voiced_frames = []
                    silent_count = 0
                    speech_frame_count = 0
                    ring.clear()
