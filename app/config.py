# -*- coding: utf-8 -*-
"""
הגדרות גלובליות לנרי – עוזר אישי קולי.
שנה כאן שמות, מפתחות, ופרמטרי האזנה בלבד.
"""

import os

# ─── שם העוזרת ────────────────────────────────────────────────
ASSISTANT_NAME_HE: str = os.getenv("ASSISTANT_NAME_HE", "נרי")
ASSISTANT_NAME_EN: str = os.getenv("ASSISTANT_NAME_EN", "nari")

# ─── מפתחות API ────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
AZURE_SPEECH_KEY: str = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION: str = os.getenv("AZURE_SPEECH_REGION", "")

# ─── קול Azure TTS ─────────────────────────────────────────────
AZURE_VOICE_NAME: str = "he-IL-HilaNeural"

# ─── הגדרות הקלטה / VAD ────────────────────────────────────────
SAMPLE_RATE: int = 16000          # Hz – נדרש על-ידי webrtcvad
VAD_CHUNK_MS: int = 30            # webrtcvad תומך ב-10/20/30 ms
VAD_SILENCE_SEC: float = 1.5     # שתיקה רצופה לסיום משפט
VAD_MAX_SPEECH_SEC: float = 20.0  # מקסימום אורך משפט
VAD_PRE_SPEECH_PAD_MS: int = 300  # padding לפני תחילת דיבור
VAD_AGGRESSIVENESS: int = 3       # 0=רגיש, 3=אגרסיבי לסינון רעש

# ─── Google Calendar ──────────────────────────────────────────────────────────
# הורד credentials.json מ-Google Cloud Console → APIs & Services → Credentials
GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE: str       = os.getenv("GOOGLE_TOKEN_FILE",       "token.json")
GOOGLE_CALENDAR_ID: str      = os.getenv("GOOGLE_CALENDAR_ID",      "primary")

# ─── מצב לחשן (trigger engine) ────────────────────────────────
WRITE_TRIGGER_LOGS: bool = True
LOGS_DIR: str = "logs"

# ─── מודלים ───────────────────────────────────────────────────
TRANSCRIPTION_MODEL: str = "gpt-4o-transcribe"
LLM_MODEL: str = "gpt-4o-mini"
