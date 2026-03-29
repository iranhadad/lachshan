# -*- coding: utf-8 -*-
"""
מנהל מצב המערכת ב-singleton.

מצבים:
  lachshan_active=False  → נרי מאזינה רק לפקודות ישירות ("נרי ...")
  lachshan_active=True   → לחשן פעיל: מאזינים לשיחת הסביבה,
                           trigger_engine רץ על כל chunk
"""

from dataclasses import dataclass, field
from typing import Optional

from trigger_engine.schemas.runtime_context import RecentIntervention
from trigger_engine.utils.time_utils import now_iso


@dataclass
class _SystemState:
    lachshan_active: bool = False
    session_id: str = ""

    # חלון תמלול לשיחה (last-N chunks)
    transcript_buffer: list[str] = field(default_factory=list)

    # זיכרון התערבויות לtrigger engine
    recent_interventions: list[RecentIntervention] = field(default_factory=list)

    # טיוטת מייל ממתינה לאישור קולי
    pending_email_draft: Optional[object] = None   # type: EmailDraft | None

    def add_transcript(self, text: str) -> None:
        self.transcript_buffer.append(text)
        if len(self.transcript_buffer) > 20:
            del self.transcript_buffer[:-20]

    def full_transcript(self) -> str:
        return "\n".join(self.transcript_buffer)

    def remember_intervention(self, intervention: RecentIntervention) -> None:
        self.recent_interventions.append(intervention)
        if len(self.recent_interventions) > 10:
            del self.recent_interventions[:-10]


# ─── Singleton ────────────────────────────────────────────────────────────────

_state = _SystemState()


def get_state() -> _SystemState:
    return _state


# ─── פונקציות עזר ────────────────────────────────────────────────────────────

def set_session_id(session_id: str) -> None:
    _state.session_id = session_id


def enable_lachshan() -> None:
    _state.lachshan_active = True


def disable_lachshan() -> None:
    _state.lachshan_active = False


def is_lachshan_active() -> bool:
    return _state.lachshan_active
