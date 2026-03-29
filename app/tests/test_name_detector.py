# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.name_detector import is_addressed_to_nari, strip_name_prefix


# ── is_addressed_to_nari ──────────────────────────────────────────────────────

class TestIsAddressedToNari:

    @pytest.mark.parametrize("text", [
        "\u05e0\u05e8\u05d9 \u05ea\u05d1\u05d3\u05e7\u05d9 \u05d0\u05ea \u05d4\u05d9\u05d5\u05de\u05df",  # נרי תבדקי את היומן
        "\u05e0\u05e8\u05d9\u05d4 \u05e2\u05e6\u05e8\u05d9",                                              # נריה עצרי
        "\u05e0\u05e8\u05d9\u05ea \u05e7\u05d1\u05e2\u05d9 \u05e4\u05d2\u05d9\u05e9\u05d4",               # נרית קבעי פגישה
        "nari check my calendar",
        "Nari stop",
    ])
    def test_true_cases(self, text):
        assert is_addressed_to_nari(text) is True, f"expected True for: {text!r}"

    @pytest.mark.parametrize("text", [
        "\u05e0\u05d5\u05e8\u05d1\u05d9 \u05ea\u05d1\u05d3\u05d5\u05e7",  # נורבי תבדוק
        "\u05de\u05d4 \u05d4\u05e9\u05e2\u05d4",                           # מה השעה
        "\u05d4\u05d9\u05d9 \u05d0\u05d9\u05da \u05d0\u05ea\u05d4",        # היי איך אתה
    ])
    def test_false_cases(self, text):
        assert is_addressed_to_nari(text) is False, f"expected False for: {text!r}"


# ── strip_name_prefix ─────────────────────────────────────────────────────────

class TestStripNamePrefix:

    @pytest.mark.parametrize("text, expected", [
        # מדויק
        ("\u05e0\u05e8\u05d9 \u05ea\u05d1\u05d3\u05e7\u05d9 \u05d0\u05ea \u05d4\u05d9\u05d5\u05de\u05df",
         "\u05ea\u05d1\u05d3\u05e7\u05d9 \u05d0\u05ea \u05d4\u05d9\u05d5\u05de\u05df"),   # נרי תבדקי את היומן → תבדקי את היומן
        ("\u05e0\u05e8\u05d9, \u05ea\u05e4\u05e2\u05d9\u05dc\u05d9 \u05dc\u05d7\u05e9\u05df",
         "\u05ea\u05e4\u05e2\u05d9\u05dc\u05d9 \u05dc\u05d7\u05e9\u05df"),                 # נרי, תפעילי לחשן → תפעילי לחשן
        # fuzzy
        ("\u05e0\u05e8\u05d9\u05d4 \u05e2\u05e6\u05e8\u05d9",
         "\u05e2\u05e6\u05e8\u05d9"),                                                      # נריה עצרי → עצרי
        ("\u05e0\u05e8\u05d9\u05ea \u05e7\u05d1\u05e2\u05d9 \u05e4\u05d2\u05d9\u05e9\u05d4",
         "\u05e7\u05d1\u05e2\u05d9 \u05e4\u05d2\u05d9\u05e9\u05d4"),                      # נרית קבעי פגישה → קבעי פגישה
        # אנגלית
        ("nari check my calendar", "check my calendar"),
        ("Nari stop", "stop"),
    ])
    def test_strip(self, text, expected):
        result = strip_name_prefix(text)
        assert result == expected, f"strip({text!r}) = {result!r}, expected {expected!r}"
