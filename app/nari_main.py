# -*- coding: utf-8 -*-
"""
נרי – לולאה ראשית.

הרצה:
    python nari_main.py           (מ-תיקיית app/)

זרימה:
  1. בדיקת הגדרות חיוניות
  2. סיכום בוקר קצר
  3. לולאת האזנה רציפה (VAD):
     a. chunk מתמלל → Whisper
     b. אם מתחיל ב"נרי" → intent_router → פעולה
     c. אחרת, אם לחשן פעיל → trigger_engine → whisper-in-ear אם נחוץ
"""

import os
import sys
import wave
import tempfile
import threading
from datetime import datetime
from typing import Optional
import time

from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk

# ─── הגדרות ──────────────────────────────────────────────────────────────────
from config import (
    OPENAI_API_KEY,
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    AZURE_VOICE_NAME,
    SAMPLE_RATE,
    WRITE_TRIGGER_LOGS,
    LOGS_DIR,
    TRANSCRIPTION_MODEL,
    LLM_MODEL,
    ASSISTANT_NAME_HE,
)

# ─── core ─────────────────────────────────────────────────────────────────────
from core.vad_listener import VADListener
from core.name_detector import is_addressed_to_nari, strip_name_prefix
from core.intent_router import route_intent, Intent
from core.system_mode_manager import (
    get_state,
    enable_lachshan,
    disable_lachshan,
    is_lachshan_active,
    set_session_id,
)

# ─── actions ──────────────────────────────────────────────────────────────────
from actions.calendar_action import get_calendar_summary
try:
    from actions.calendar_action import add_event
except ImportError:
    def add_event(command_text: str) -> str:  # type: ignore[misc]
        return "הוספת אירוע לא ממומשת עדיין."
from actions.gmail_action import (
    compose_draft,
    draft_to_speech_preview,
    is_confirmation,
    is_cancellation,
    send_draft,
    read_inbox,
)

# ─── morning brief ────────────────────────────────────────────────────────────
from morning_brief import get_morning_brief

# ─── trigger engine (לא נוגעים בו) ───────────────────────────────────────────
from trigger_engine.runner import run_trigger_engine_on_text
from trigger_engine.schemas.runtime_context import RecentIntervention
from trigger_engine.schemas.intervention_log import (
    ConversationContextSnapshot,
    EvaluationTrace,
    InterventionLogRecord,
)
from trigger_engine.logging.write_jsonl_log import write_jsonl_log
from trigger_engine.utils.id_utils import create_intervention_id
from trigger_engine.utils.time_utils import now_iso


# ═══════════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_env() -> None:
    missing = [
        name
        for name, val in [
            ("OPENAI_API_KEY",    OPENAI_API_KEY),
            ("AZURE_SPEECH_KEY",  AZURE_SPEECH_KEY),
            ("AZURE_SPEECH_REGION", AZURE_SPEECH_REGION),
        ]
        if not val
    ]
    if missing:
        print(f"[שגיאה] משתני סביבה חסרים: {', '.join(missing)}")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Audio I/O  (שמור מ-lachshan.py)
# ═══════════════════════════════════════════════════════════════════════════════

_openai_client: Optional[OpenAI] = None

# היסטוריית שיחה חופשית עם נרי
conversation_history: list[dict] = []

def _build_nari_system_prompt() -> str:
    current_time = datetime.now().strftime("%H:%M")
    current_date = datetime.now().strftime("%d/%m/%Y")
    return (
        f"השעה הנוכחית היא {current_time}. התאריך הוא {current_date}. "
        "אתה נרי, עוזרת אישית קולית חכמה. "
        "עני בעברית, בתשובות קצרות ומדויקות המתאימות לדיבור. "
        "אל תשתמשי ברשימות או כוכביות – דברי בצורה טבעית."
    )

# נעילה: מונע תמלול קול של נרי עצמה בזמן שהיא מדברת
_is_speaking = threading.Event()


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _log(tag: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{tag}] {msg}")


def speak(text: str) -> None:
    """
    Azure TTS – קול Hila עברי.
    רץ ב-thread נפרד; מאזין במקביל למיקרופון.
    אם מזוהה דיבור תוך כדי — עוצר את ה-TTS מיד.
    """
    _is_speaking.set()
    synthesizer_ref: list = []   # מאחסן את ה-synthesizer לצורך עצירה

    def _tts_thread() -> None:
        try:
            speech_config = speechsdk.SpeechConfig(
                subscription=AZURE_SPEECH_KEY,
                region=AZURE_SPEECH_REGION,
            )
            speech_config.speech_synthesis_voice_name = AZURE_VOICE_NAME
            audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            synth = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )
            synthesizer_ref.append(synth)
            result = synth.speak_text_async(text).get()
            if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                _log("TTS", f"שגיאה: {result.reason}")
        except Exception as exc:
            _log("TTS", f"חריגה: {exc}")
        finally:
            _is_speaking.clear()

    tts = threading.Thread(target=_tts_thread, daemon=True)
    tts.start()

    # האזן למיקרופון תוך כדי דיבור — אם מזוהה קול, עצור
    from core.vad_listener import VADListener
    monitor = VADListener()
    monitor.start()
    try:
        while tts.is_alive():
            chunk = monitor.get_next_chunk(timeout=0.1)
            if chunk is not None and _is_speaking.is_set():
                # המשתמש דיבר — עצור TTS
                if synthesizer_ref:
                    synthesizer_ref[0].stop_speaking_async()
                _is_speaking.clear()
                break
    finally:
        monitor.stop()
        tts.join(timeout=2)
    # cooldown: מניעת echo – אל תקלוט דיבור מיד אחרי תשובה
    _is_speaking.set()
    time.sleep(2)
    _is_speaking.clear()
    print("[נרי] מאזינה...")


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


def transcribe_file(wav_path: str) -> str:
    """Whisper STT – מחזיר תמלול עברי. מחזיר '' אם מזוהה ביטוי רעש נפוץ."""
    with open(wav_path, "rb") as audio_file:
        transcript = _get_openai_client().audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=audio_file,
            prompt="השיחה היא בעברית. נא לתמלל בעברית.",
        )
    text = transcript.text.strip()
    if any(phrase in text for phrase in _NOISE_PHRASES):
        return ""
    return text


def _pcm_to_wav(pcm_bytes: bytes) -> str:
    """שומר bytes גולמיים (PCM int16) לקובץ WAV זמני. מחזיר נתיב."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # int16
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return tmp.name


# ═══════════════════════════════════════════════════════════════════════════════
# Trigger engine helpers  (שמור מ-lachshan.py)
# ═══════════════════════════════════════════════════════════════════════════════

def _pick_debug_result(trigger_output):
    if not trigger_output.results:
        return None
    if trigger_output.decision.should_intervene and trigger_output.decision.selected_trigger_id:
        for r in trigger_output.results:
            if r.trigger_id == trigger_output.decision.selected_trigger_id:
                return r
    blocked = [r for r in trigger_output.results if r.blocked_by]
    if blocked:
        return sorted(blocked, key=lambda r: (r.intervention_score, r.confidence), reverse=True)[0]
    return sorted(trigger_output.results, key=lambda r: (r.intervention_score, r.confidence), reverse=True)[0]


def _log_trigger_decision(
    session_id: str,
    chunk_text: str,
    trigger_run_result,
    intervention_id: str,
) -> None:
    if not WRITE_TRIGGER_LOGS:
        return

    trigger_output   = trigger_run_result.output
    detected_entities = trigger_run_result.detected_entities
    current_topic    = trigger_run_result.current_topic
    debug_result     = _pick_debug_result(trigger_output)

    trigger_type     = trigger_output.decision.selected_trigger_id or "none"
    trigger_version  = trigger_output.decision.selected_trigger_version or "n/a"
    confidence       = trigger_output.decision.confidence or (debug_result.confidence if debug_result else 0.0)
    intervention_score = trigger_output.decision.intervention_score or (
        debug_result.intervention_score if debug_result else 0.0
    )
    whisper_text = (
        trigger_output.decision.selected_candidate.text
        if trigger_output.decision.selected_candidate
        else (debug_result.candidate_whisper.text if debug_result and debug_result.candidate_whisper else "")
    )
    blocked_by = (
        debug_result.blocked_by
        if debug_result and debug_result.blocked_by
        else trigger_output.decision.blocked_by
    )
    feature_scores    = debug_result.feature_scores if debug_result else {}
    reasoning_summary = (
        debug_result.reasoning_summary if debug_result else trigger_output.decision.decision_reason
    )
    candidate_count   = len([r for r in trigger_output.results if r.candidate_whisper])
    competing_triggers = [r.trigger_id for r in trigger_output.results]

    record = InterventionLogRecord(
        session_id=session_id,
        intervention_id=intervention_id,
        timestamp=now_iso(),
        trigger_type=trigger_type,
        trigger_version=trigger_version,
        latency_mode="low_latency",
        source_text_window=chunk_text,
        conversation_context=ConversationContextSnapshot(
            current_topic=current_topic or "live_transcript",
            open_questions=[],
            facts_snapshot=[],
            recent_events=["nari_vad_loop"],
            recent_memory_snapshot=[],
        ),
        detected_entities=detected_entities,
        intervention_score=intervention_score,
        confidence=confidence,
        reasoning_summary=reasoning_summary,
        whisper_text=whisper_text,
        was_played=trigger_output.decision.should_intervene,
        audio_delivery_status="played" if trigger_output.decision.should_intervene else "skipped",
        evaluation_trace=EvaluationTrace(
            feature_scores=feature_scores,
            blocked_by=blocked_by,
            candidate_count=candidate_count,
            competing_triggers=competing_triggers,
        ),
    )
    write_jsonl_log(f"{LOGS_DIR}/interventions_log.jsonl", record)


# ═══════════════════════════════════════════════════════════════════════════════
# Intent handlers
# ═══════════════════════════════════════════════════════════════════════════════

_QUESTION_WORDS = ("מה", "איך", "האם", "למה", "מתי")

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
    """שולח ל-LLM ומחזיר date_offset_days (מספר שלם). ברירת מחדל: 0."""
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        system = f"היום הוא {today_str}. " + _DATE_OFFSET_SYSTEM
        resp = _get_openai_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": command_text},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        return int(resp.choices[0].message.content.strip())
    except Exception:
        return 0


def _is_direct_question(text: str) -> bool:
    """בודק אם הטקסט הוא שאלה ישירה (סימן שאלה או מילת שאלה)."""
    if "?" in text:
        return True
    first_word = text.split()[0] if text.split() else ""
    return first_word in _QUESTION_WORDS


def _ask_nari_free(command_text: str) -> str:
    """LLM עם זיכרון שיחה: עונה על שאלה/שיחה חופשית בעברית."""
    global conversation_history
    try:
        messages: list[dict] = [{"role": "system", "content": _build_nari_system_prompt()}]
        messages += conversation_history[-10:]
        messages.append({"role": "user", "content": command_text})

        resp = _get_openai_client().chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
        )
        answer = resp.choices[0].message.content.strip()
        conversation_history.append({"role": "user", "content": command_text})
        conversation_history.append({"role": "assistant", "content": answer})
        return answer
    except Exception:
        return "לא הצלחתי לענות על זה."


def _handle_nari_command(command_text: str) -> None:
    """מנתב פקודה שמוכתבת לנרי לפעולה המתאימה."""
    state = get_state()
    result = route_intent(command_text)

    if result.intent == Intent.STOP:
        return

    if result.intent == Intent.ENABLE_LACHSHAN:
        enable_lachshan()
        speak("לחשן הופעל. אני מאזינה.")
        _log("נרי", "לחשן הופעל")

    elif result.intent == Intent.DISABLE_LACHSHAN:
        disable_lachshan()
        speak("לחשן כובה.")
        _log("נרי", "לחשן כובה")

    elif result.intent == Intent.CALENDAR:
        speak("רגע, בודקת את היומן.")
        offset = _resolve_date_offset(command_text)
        summary = get_calendar_summary(offset)
        speak(summary)
        _log("נרי/יומן", summary)

    elif result.intent == Intent.READ_EMAIL:
        speak("רגע, בודקת את המיילים.")
        summary = read_inbox()
        speak(summary)
        _log("נרי/מייל-קריאה", summary)

    elif result.intent == Intent.EMAIL:
        speak("מכינה טיוטת מייל.")
        draft = compose_draft(command_text)
        if draft is None:
            speak("לא הצלחתי להכין את המייל.")
            return
        state.pending_email_draft = draft
        preview = draft_to_speech_preview(draft)
        speak(preview)
        _log("נרי/מייל", "טיוטה מוכנה – ממתינה לאישור")

    elif result.intent == Intent.ADD_EVENT:
        speak("רגע, מוסיפה ליומן...")
        confirmation = add_event(command_text)
        speak(confirmation)
        _log("נרי/יומן-הוסף", confirmation)

    elif result.intent == Intent.CONVERSATION:
        answer = _ask_nari_free(command_text)
        speak(answer)
        _log("נרי/שיחה", f"Q: {command_text[:50]} → {answer[:60]}")

    else:
        # UNKNOWN – fallback לשיחה חופשית
        answer = _ask_nari_free(command_text)
        speak(answer)
        _log("נרי/LLM", f"Q: {command_text[:50]} → {answer[:60]}")


def _handle_email_confirmation(text: str) -> bool:
    """
    בודק אם הטקסט הוא תשובה לאישור/ביטול מייל.
    מחזיר True אם הטקסט טופל (וניתן לדלג על עיבוד רגיל).
    """
    state = get_state()
    if state.pending_email_draft is None:
        return False

    if is_confirmation(text):
        result_msg = send_draft(state.pending_email_draft)
        state.pending_email_draft = None
        speak(result_msg)
        _log("נרי/מייל", result_msg)
        return True

    if is_cancellation(text):
        state.pending_email_draft = None
        speak("בסדר, ביטלתי את המייל.")
        _log("נרי/מייל", "ביטול")
        return True

    # לא זיהינו תשובה ברורה – שואלים שוב
    speak("לא הבנתי. האם לשלוח את המייל? אמור כן או לא.")
    return True


def _handle_lachshan_chunk(chunk_text: str) -> None:
    """מצב לחשן: מריץ trigger engine ומשמיע whisper אם נחוץ."""
    state = get_state()
    state.add_transcript(chunk_text)

    try:
        run_result = run_trigger_engine_on_text(
            text=chunk_text,
            session_id=state.session_id,
            current_topic="live_transcript",
            detected_entities=None,
            recent_interventions=state.recent_interventions,
        )
        trigger_output    = run_result.output
        intervention_id   = create_intervention_id()

        _log_trigger_decision(
            session_id=state.session_id,
            chunk_text=chunk_text,
            trigger_run_result=run_result,
            intervention_id=intervention_id,
        )

        if (
            trigger_output.decision.should_intervene
            and trigger_output.decision.selected_candidate is not None
        ):
            whisper_text = trigger_output.decision.selected_candidate.text
            _log("לחשן", whisper_text)
            speak(whisper_text)

            state.remember_intervention(RecentIntervention(
                intervention_id=intervention_id,
                trigger_type=trigger_output.decision.selected_trigger_id or "unknown",
                whisper_text=whisper_text,
                timestamp=now_iso(),
                target_topic=trigger_output.decision.selected_candidate.target_topic,
            ))
        else:
            _log("לחשן", f"אין התערבות | {chunk_text[:60]}")

    except Exception as exc:
        _log("לחשן/שגיאה", str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    _validate_env()

    # הכן תיקיית לוגים
    os.makedirs(LOGS_DIR, exist_ok=True)

    # session ID
    session_id = create_intervention_id()
    set_session_id(session_id)

    _log("נרי", f"v1.0  session={session_id}")
    _log("נרי", "מכין סיכום בוקר...")

    # ─── סיכום בוקר ──────────────────────────────────────────────────────────
    try:
        brief = get_morning_brief()
        _log("בוקר", brief)
        speak(brief)
    except Exception as exc:
        _log("בוקר/שגיאה", str(exc))

    # ─── לולאת האזנה רציפה ───────────────────────────────────────────────────
    listener = VADListener()
    listener.start()
    print(f"\nמאזינה... (אמור '{ASSISTANT_NAME_HE} ...' לפקודה ישירה)")
    print("Ctrl+C לעצירה\n")

    try:
        while True:
            # חכה ל-chunk שמע (timeout=2 כדי לא לחסום לנצח)
            pcm_chunk = listener.get_next_chunk(timeout=2)
            if pcm_chunk is None:
                continue

            # דלג על תמלול בזמן שנרי מדברת (מניעת echo)
            if _is_speaking.is_set():
                continue

            # המרה ל-WAV זמני
            wav_path = _pcm_to_wav(pcm_chunk)
            try:
                text = transcribe_file(wav_path)
            except Exception as exc:
                _log("STT/שגיאה", str(exc))
                continue
            finally:
                os.unlink(wav_path)

            if not text:
                continue

            _log("STT", text)

            # ── מייל ממתין לאישור? ──────────────────────────────────────────
            if _handle_email_confirmation(text):
                continue

            # ── פילטר רעש: חייב ≥2 מילים + שם נרי ──────────────────────────
            if len(text.split()) < 2 or not is_addressed_to_nari(text):
                if is_lachshan_active():
                    _handle_lachshan_chunk(text)
                continue

            # ── פקודה ישירה לנרי? ────────────────────────────────────────────
            if is_addressed_to_nari(text):
                command = strip_name_prefix(text)
                _handle_nari_command(command)
                continue

            # ── שאלה ישירה (ללא שם נרי)? ────────────────────────────────────
            if _is_direct_question(text):
                answer = _ask_nari_free(text)
                speak(answer)
                _log("נרי/שאלה", f"Q: {text[:50]} → {answer[:60]}")
                continue

            # ── מצב לחשן ────────────────────────────────────────────────────
            if is_lachshan_active():
                _handle_lachshan_chunk(text)

    except KeyboardInterrupt:
        print("\n")
        _log("נרי", "מסיים.")
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
