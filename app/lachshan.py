# -*- coding: utf-8 -*-
import os
import time
import sounddevice as sd
from scipy.io.wavfile import write
from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk

from trigger_engine.logging.write_jsonl_log import write_jsonl_log
from trigger_engine.runner import run_trigger_engine_on_text
from trigger_engine.schemas.intervention_log import (
    ConversationContextSnapshot,
    EvaluationTrace,
    InterventionLogRecord,
)
from trigger_engine.schemas.runtime_context import RecentIntervention
from trigger_engine.utils.id_utils import create_intervention_id
from trigger_engine.utils.time_utils import now_iso

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set")

if not AZURE_SPEECH_KEY:
    raise ValueError("AZURE_SPEECH_KEY is not set")

if not AZURE_SPEECH_REGION:
    raise ValueError("AZURE_SPEECH_REGION is not set")

client = OpenAI(api_key=OPENAI_API_KEY)

sample_rate = 16000
chunk_duration = 8
max_rounds = 5

use_trigger_engine_preview = True
write_trigger_logs = True

full_transcript_parts = []
log_lines = []
recent_interventions_memory: list[RecentIntervention] = []


def log(msg: str):
    print(msg)
    log_lines.append(msg)


def save_output():
    with open("output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))


def speak(text: str):
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=AZURE_SPEECH_KEY,
            region=AZURE_SPEECH_REGION
        )
        speech_config.speech_synthesis_voice_name = "he-IL-HilaNeural"

        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        result = synthesizer.speak_text_async(text).get()

        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            log(f"שגיאת דיבור Azure: {result.reason}")

    except Exception as e:
        log(f"שגיאת Azure TTS: {str(e)}")


def record_chunk(filename: str, duration: int):
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16"
    )
    sd.wait()
    write(filename, sample_rate, recording)


def transcribe_file(filename: str) -> str:
    with open(filename, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file,
            prompt="השיחה היא בעברית. נא לתמלל בעברית."
        )
    return transcript.text.strip()


def ask_lachshan(full_text: str, round_number: int) -> str:
    if round_number % 2 == 0:
        instruction = """
תן תקציר מצב קצר:
- מה נסגר
- מה פתוח
- עד 2 שורות
"""
    else:
        instruction = """
תן עצה קצרה אחת למשתמש:
- בעברית בלבד
- עד 12 מילים
- בלי הקדמות
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
אתה 'לחשן' - עוזר בזמן אמת.
ענה רק בעברית.

להלן השיחה עד כה:
{full_text}

{instruction}
"""
    )

    return response.output_text.strip()


def remember_intervention(
    trigger_output_wrapper,
    intervention_id: str,
) -> None:
    trigger_output = trigger_output_wrapper.output

    if (
        not trigger_output.decision.should_intervene
        or trigger_output.decision.selected_candidate is None
        or trigger_output.decision.selected_trigger_id is None
    ):
        return

    recent_interventions_memory.append(
        RecentIntervention(
            intervention_id=intervention_id,
            trigger_type=trigger_output.decision.selected_trigger_id,
            whisper_text=trigger_output.decision.selected_candidate.text,
            timestamp=now_iso(),
            target_topic=trigger_output.decision.selected_candidate.target_topic,
        )
    )

    if len(recent_interventions_memory) > 10:
        del recent_interventions_memory[:-10]


def pick_debug_result(trigger_output):
    if not trigger_output.results:
        return None

    if trigger_output.decision.should_intervene and trigger_output.decision.selected_trigger_id:
        for result in trigger_output.results:
            if result.trigger_id == trigger_output.decision.selected_trigger_id:
                return result

    blocked_results = [result for result in trigger_output.results if result.blocked_by]
    if blocked_results:
        return sorted(
            blocked_results,
            key=lambda r: (r.intervention_score, r.confidence),
            reverse=True,
        )[0]

    return sorted(
        trigger_output.results,
        key=lambda r: (r.intervention_score, r.confidence),
        reverse=True,
    )[0]


def write_trigger_decision_log(
    session_id: str,
    round_number: int,
    chunk_text: str,
    trigger_output_wrapper,
    intervention_id: str,
):
    if not write_trigger_logs:
        return

    trigger_output = trigger_output_wrapper.output
    detected_entities = trigger_output_wrapper.detected_entities
    current_topic = trigger_output_wrapper.current_topic

    debug_result = pick_debug_result(trigger_output)

    trigger_type = trigger_output.decision.selected_trigger_id or "none"
    trigger_version = trigger_output.decision.selected_trigger_version or "n/a"
    confidence = trigger_output.decision.confidence or (debug_result.confidence if debug_result else 0.0)
    intervention_score = trigger_output.decision.intervention_score or (
        debug_result.intervention_score if debug_result else 0.0
    )
    whisper_text = (
        trigger_output.decision.selected_candidate.text
        if trigger_output.decision.selected_candidate is not None
        else (debug_result.candidate_whisper.text if debug_result and debug_result.candidate_whisper else "")
    )

    if debug_result is not None and debug_result.blocked_by:
        blocked_by = debug_result.blocked_by
    else:
        blocked_by = trigger_output.decision.blocked_by

    feature_scores = debug_result.feature_scores if debug_result is not None else {}
    reasoning_summary = (
        debug_result.reasoning_summary
        if debug_result is not None
        else trigger_output.decision.decision_reason
    )

    candidate_count = len(
        [result for result in trigger_output.results if result.candidate_whisper is not None]
    )
    competing_triggers = [result.trigger_id for result in trigger_output.results]

    log_record = InterventionLogRecord(
        session_id=session_id,
        intervention_id=intervention_id,
        timestamp=now_iso(),
        trigger_type=trigger_type,
        trigger_version=trigger_version,
        latency_mode="low_latency",
        source_text_window=chunk_text,
        conversation_context=ConversationContextSnapshot(
            current_topic=current_topic or f"round_{round_number}",
            open_questions=[],
            facts_snapshot=[],
            recent_events=["live_trigger_engine_evaluation"],
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

    write_jsonl_log("logs/interventions_log.jsonl", log_record)


log("לחשן v0.8 התחיל")
log("")
save_output()

session_id = create_intervention_id()

for round_number in range(1, max_rounds + 1):
    audio_filename = f"round_{round_number}.wav"

    log(f"--- סבב {round_number}/{max_rounds} ---")
    log(f"מקליט {chunk_duration} שניות")
    save_output()

    record_chunk(audio_filename, chunk_duration)

    log("שולח לתמלול")
    save_output()

    try:
        chunk_text = transcribe_file(audio_filename)
    except Exception as e:
        log(f"שגיאת תמלול: {str(e)}")
        save_output()
        continue

    if not chunk_text:
        chunk_text = "[לא זוהה דיבור]"

    full_transcript_parts.append(chunk_text)
    full_text = "\n".join(full_transcript_parts)

    log("")
    log("תמלול:")
    log(chunk_text)
    log("")

    if use_trigger_engine_preview:
        try:
            trigger_run_result = run_trigger_engine_on_text(
                text=chunk_text,
                session_id=session_id,
                current_topic="live_transcript",
                detected_entities=None,
                recent_interventions=recent_interventions_memory,
            )

            trigger_output = trigger_run_result.output
            current_intervention_id = create_intervention_id()

            log("Trigger Engine Decision:")
            log(str(trigger_output.decision))
            log(f"Detected Entities: {trigger_run_result.detected_entities}")
            log(f"Recent Interventions In Memory: {len(recent_interventions_memory)}")

            if (
                trigger_output.decision.should_intervene
                and trigger_output.decision.selected_candidate is not None
            ):
                log(f"🧠 Trigger Whisper: {trigger_output.decision.selected_candidate.text}")
            else:
                log("🧠 Trigger Whisper: [no intervention]")

            log("")

            write_trigger_decision_log(
                session_id=session_id,
                round_number=round_number,
                chunk_text=chunk_text,
                trigger_output_wrapper=trigger_run_result,
                intervention_id=current_intervention_id,
            )

            remember_intervention(
                trigger_output_wrapper=trigger_run_result,
                intervention_id=current_intervention_id,
            )

        except Exception as e:
            log(f"שגיאת Trigger Engine: {str(e)}")
            log("")

    try:
        whisper = ask_lachshan(full_text, round_number)

        if round_number % 2 == 0:
            log("תקציר ביניים:")
        else:
            log("עצת הלחשן:")

        log(whisper)
        log(f"🎧 לחשן: {whisper}")
        save_output()

        speak(whisper)

    except Exception as e:
        log(f"שגיאת ניתוח: {str(e)}")

    log("")
    save_output()
    time.sleep(1)

log("=== סיום השיחה ===")
log("")

full_text = "\n".join(full_transcript_parts)

try:
    final_summary = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
ענה בעברית.

זה תמלול שיחה:
{full_text}

כתוב סיכום:
1. מה נסגר
2. מה פתוח
3. מה כדאי לעשות
"""
    ).output_text.strip()

    log("סיכום סופי:")
    log(final_summary)
    log(f"🎧 לחשן: {final_summary}")
    save_output()

    speak(final_summary)

except Exception as e:
    log(f"שגיאת סיכום: {str(e)}")

save_output()
print("\nSaved to output.txt")