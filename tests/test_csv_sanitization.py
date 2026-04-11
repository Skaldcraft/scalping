"""
tests/test_csv_sanitization.py
=============================
Tests for CSV sanitization in data/fetcher.py.
"""

import logging
import pytest
import pandas as pd
from data.fetcher import _strip_formula_prefix, _sanitize_dataframe, _FORMULA_PREFIXES


class TestStripFormulaPrefix:
    def test_formula_equals_prefix(self):
        assert _strip_formula_prefix("=CMD|'/C calc'!A0") == " =CMD|'/C calc'!A0"
        assert _strip_formula_prefix("=HYPERLINK(...)") == " =HYPERLINK(...)"

    def test_formula_plus_prefix(self):
        assert _strip_formula_prefix("+SELECT * FROM users") == " +SELECT * FROM users"

    def test_formula_minus_prefix(self):
        assert _strip_formula_prefix("-1+2") == " -1+2"

    def test_formula_at_prefix(self):
        assert _strip_formula_prefix("@SUM(A1:A10)") == " @SUM(A1:A10)"

    def test_normal_number_string(self):
        assert _strip_formula_prefix("100.50") == "100.50"

    def test_normal_text(self):
        assert _strip_formula_prefix("AAPL") == "AAPL"

    def test_empty_string(self):
        assert _strip_formula_prefix("") == ""

    def test_whitespace_only(self):
        assert _strip_formula_prefix("   ") == ""

    def test_whitespace_prefix_formula(self):
        assert _strip_formula_prefix("  =CMD") == " =CMD"
        assert _strip_formula_prefix("  +SELECT") == " +SELECT"
        assert _strip_formula_prefix("  -1+2") == " -1+2"


class TestSanitizeDataFrame:
    def test_clean_dataframe_unchanged(self):
        df = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000.0, 1100.0],
        })
        result = _sanitize_dataframe(df, "TEST")
        pd.testing.assert_frame_equal(result, df)

    def test_formula_in_string_column_neutralized(self):
        df = pd.DataFrame({
            "open": ["=CMD|'/C calc'!A0", "100.0"],
            "high": ["+SELECT * FROM", "101.0"],
            "low": ["-1+2", "99.0"],
            "close": ["@SUM(A1:A10)", "100.5"],
        }, dtype=object)
        result = _sanitize_dataframe(df, "TEST")
        assert result["open"].iloc[0] == " =CMD|'/C calc'!A0"
        assert result["high"].iloc[0] == " +SELECT * FROM"
        assert result["low"].iloc[0] == " -1+2"
        assert result["close"].iloc[0] == " @SUM(A1:A10)"

    def test_numeric_columns_unchanged(self):
        df = pd.DataFrame({
            "open": [100.0, 101.0],
            "close": [100.5, 101.5],
        })
        result = _sanitize_dataframe(df, "TEST")
        pd.testing.assert_frame_equal(result, df)

    def test_mixed_columns_only_strings_sanitized(self):
        df = pd.DataFrame({
            "open": [100.0, "=CMD|'/Ccalc'!A0"],
            "close": [100.5, 101.5],
        }, dtype=object)
        df["close"] = df["close"].astype(float)
        result = _sanitize_dataframe(df, "TEST")
        assert result["open"].iloc[0] == "100.0"
        assert result["open"].iloc[1] == " =CMD|'/Ccalc'!A0"

    def test_sanitization_count_logged(self, caplog):
        caplog.set_level(logging.WARNING, logger="data.fetcher")
        df = pd.DataFrame({
            "open": ["=CMD|'/C calc'!A0", "=HYPERLINK(...)"],
            "close": [100.5, 101.5],
        }, dtype=object)
        _sanitize_dataframe(df, "INJECT")
        assert "INJECT" in caplog.text
        assert "sanitized" in caplog.text
