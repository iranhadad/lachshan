# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from unittest.mock import MagicMock, patch

from core.intent_router import route_intent, Intent


def _mock_response(intent_str: str, confidence: float = 0.95) -> MagicMock:
    """בונה mock של תגובת OpenAI עם JSON מסוים."""
    payload = json.dumps({"intent": intent_str, "confidence": confidence})
    msg = MagicMock()
    msg.content = payload
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.parametrize("text, expected_intent", [
    ("\u05de\u05d4 \u05d9\u05e9 \u05dc\u05d9 \u05d4\u05d9\u05d5\u05dd",          Intent.CALENDAR),        # מה יש לי היום
    ("\u05ea\u05e7\u05e8\u05d0\u05d9 \u05de\u05d9\u05d9\u05dc\u05d9\u05dd",       Intent.READ_EMAIL),      # תקראי מיילים
    ("\u05ea\u05e7\u05d1\u05e2\u05d9 \u05e4\u05d2\u05d9\u05e9\u05d4 \u05e2\u05dd \u05d9\u05e0\u05d9\u05d1 \u05de\u05d7\u05e8 \u05d1-10",
                                                                                   Intent.ADD_EVENT),       # תקבעי פגישה עם יניב מחר ב-10
    ("\u05e9\u05dc\u05d7\u05d9 \u05de\u05d9\u05d9\u05dc \u05dc\u05d3\u05e0\u05d9", Intent.EMAIL),          # שלחי מייל לדני
    ("\u05d1\u05d5\u05d0 \u05e0\u05d7\u05e9\u05d5\u05d1 \u05d9\u05d7\u05d3 \u05e2\u05dc \u05d4\u05e4\u05e8\u05d5\u05d9\u05e7\u05d8",
                                                                                   Intent.CONVERSATION),    # בוא נחשוב יחד על הפרויקט
    ("\u05ea\u05e4\u05e2\u05d9\u05dc\u05d9 \u05dc\u05d7\u05e9\u05df",             Intent.ENABLE_LACHSHAN), # תפעילי לחשן
])
def test_route_intent(text, expected_intent):
    mock_resp = _mock_response(expected_intent.value)
    with patch("core.intent_router._get_client") as mock_get_client:
        mock_get_client.return_value.chat.completions.create.return_value = mock_resp
        result = route_intent(text)
    assert result.intent == expected_intent, (
        f"route_intent({text!r}) = {result.intent}, expected {expected_intent}"
    )
    assert result.command_text == text
    assert 0.0 <= result.confidence <= 1.0
