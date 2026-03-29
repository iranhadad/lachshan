# -*- coding: utf-8 -*-
"""
סיכום בוקר – מוצג בעליית מערכת.
"""

from datetime import datetime


def get_morning_brief() -> str:
    """ברכה לפי שעה — ללא LLM."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "בוקר טוב!"
    if 12 <= hour < 17:
        return "צהריים טובים!"
    if 17 <= hour < 21:
        return "ערב טוב!"
    return "לילה טוב!"
