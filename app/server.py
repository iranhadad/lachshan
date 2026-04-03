# -*- coding: utf-8 -*-
"""
שרת FastAPI עבור נרי – עטיפה למובייל.
הרצה: uvicorn server:app --host 0.0.0.0 --port 8000
"""

import os
import sys
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

from config import OPENAI_API_KEY, LLM_MODEL, TRANSCRIPTION_MODEL
from core.intent_router import route_intent, Intent
from actions.calendar_action import get_calendar_summary, add_event
from actions.gmail_action import compose_draft, draft_to_speech_preview, read_inbox
from trigger_engine.runner import run_trigger_engine_on_text

from openai import OpenAI

app = FastAPI(title="נרי API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
def root():
    index_path = os.path.join(_STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"message": "נרי API פעיל. אין ממשק מובייל — הנח index.html בתיקיית app/static/"}


_openai_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


class CommandRequest(BaseModel):
    text: str


_NOISE_PHRASES = [
    "השיחה היא בעברית",
    "תודה על הצפייה",
    "תודה לך",
    "שתהיה לך יום טוב",
    "להתראות",
    ".subtitles",
    "Subtitles",
    "מוזיקה",
]


async def _save_upload_to_temp(file: UploadFile, suffix: str) -> str:
    content = await file.read()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return tmp.name


def _transcribe(file_path: str) -> str:
    with open(file_path, "rb") as f:
        transcript = _get_client().audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=f,
            prompt="השיחה היא בעברית. נא לתמלל בעברית.",
        )
    text = transcript.text.strip()
    if any(phrase in text for phrase in _NOISE_PHRASES):
        return ""
    return text


_DATE_OFFSET_SYSTEM = (
    "החזר מספר שלם בלבד — כמה ימים מהיום מדובר. "
    "0=היום, 1=מחר, -1=אתמול. "
    "דוגמאות: "
    "'מה יש לי היום' → 0 | "
    "'מה יש לי מחר' → 1 | "
    "'מה היה לי אתמול' → -1 | "
    "'מה יש לי ביום חמישי' → חשב לפי התאריך הנוכחי"
)


def _resolve_date_offset(command_text: str) -> int:
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        system = f"היום הוא {today_str}. " + _DATE_OFFSET_SYSTEM
        resp = _get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": command_text},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        return int(resp.choices[0].message.content.strip())
    except Exception:
        return 0


def _ask_nari_free(command_text: str) -> str:
    try:
        current_time = datetime.now().strftime("%H:%M")
        current_date = datetime.now().strftime("%d/%m/%Y")
        system_prompt = (
            f"השעה הנוכחית היא {current_time}. התאריך הוא {current_date}. "
            "אתה נרי, עוזרת אישית קולית חכמה. "
            "עני בעברית, בתשובות קצרות ומדויקות המתאימות לדיבור. "
            "אל תשתמשי ברשימות או כוכביות – דברי בצורה טבעית."
        )
        resp = _get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": command_text},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return "לא הצלחתי לענות על זה."


def _execute_command(text: str) -> str:
    """מנתב פקודה לפי כוונה ומחזיר תשובה כטקסט."""
    result = route_intent(text)
    account = result.account  # ← חשבון שזוהה (ארגוני/אישי)

    if result.intent == Intent.STOP:
        return "מפסיקה."

    if result.intent == Intent.ENABLE_LACHSHAN:
        return "לחשן הופעל. אני מאזינה."

    if result.intent == Intent.DISABLE_LACHSHAN:
        return "לחשן כובה."

    if result.intent == Intent.CALENDAR:
        offset = _resolve_date_offset(text)
        return get_calendar_summary(offset, account=account)

    if result.intent == Intent.ADD_EVENT:
        return add_event(text, account=account)

    if result.intent == Intent.READ_EMAIL:
        return read_inbox(account=account)

    if result.intent == Intent.EMAIL:
        draft = compose_draft(text, account=account)
        if draft is None:
            return "לא הצלחתי להכין את המייל."
        return draft_to_speech_preview(draft)

    return _ask_nari_free(text)


@app.post("/speak")
def speak(req: CommandRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="טקסט ריק")
    try:
        response = _get_client().audio.speech.create(
            model="tts-1",
            voice="nova",
            input=req.text.strip(),
        )
        from fastapi.responses import Response
        return Response(content=response.content, media_type="audio/mpeg")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"שגיאת TTS: {exc}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not (filename.endswith(".wav") or filename.endswith(".webm")):
        raise HTTPException(status_code=400, detail="נדרש קובץ wav או webm")
    suffix = ".wav" if filename.endswith(".wav") else ".webm"
    tmp_path = await _save_upload_to_temp(file, suffix)
    try:
        text = _transcribe(tmp_path)
        return {"text": text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"שגיאת תמלול: {exc}")
    finally:
        os.unlink(tmp_path)


@app.post("/command")
def command(req: CommandRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="טקסט ריק")
    try:
        response = _execute_command(req.text.strip())
        return {"response": response}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"שגיאת עיבוד: {exc}")


@app.post("/lachshan")
async def lachshan(file: UploadFile = File(...)):
    filename = file.filename or ""
    suffix = ".wav" if filename.endswith(".wav") else ".webm"
    tmp_path = await _save_upload_to_temp(file, suffix)
    try:
        text = _transcribe(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"שגיאת תמלול: {exc}")
    finally:
        os.unlink(tmp_path)

    if not text:
        return {"whisper": "", "triggered": False}

    try:
        run_result = run_trigger_engine_on_text(
            text=text,
            session_id="mobile_session",
            current_topic="live_transcript",
        )
        decision = run_result.output.decision
        if decision.should_intervene and decision.selected_candidate is not None:
            return {"whisper": decision.selected_candidate.text, "triggered": True}
        return {"whisper": "", "triggered": False}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"שגיאת trigger engine: {exc}")
