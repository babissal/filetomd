"""Tests for the quality scorer module."""

import pytest

from fileconverter.utils.quality_scorer import (
    score_quality,
    _word_density,
    _garbled_ratio,
    _content_length_score,
    _whitespace_score,
    _structure_score,
)


# --- Individual heuristic tests ---


class TestWordDensity:
    def test_all_words(self):
        assert _word_density("hello world this is text") == 1.0

    def test_mixed_tokens(self):
        # 3 words out of 5 tokens
        score = _word_density("hello 123 world ?? test")
        assert 0.5 <= score <= 0.7

    def test_no_words(self):
        assert _word_density("123 456 !!! ???") == 0.0

    def test_empty(self):
        assert _word_density("") == 0.0

    def test_single_chars_not_counted(self):
        # Single chars like "a" are not counted as dictionary-like words
        score = _word_density("a b c d e")
        assert score == 0.0


class TestGarbledRatio:
    def test_clean_text(self):
        assert _garbled_ratio("This is clean normal text") == 1.0

    def test_all_garbled(self):
        score = _garbled_ratio("@#$%^ &*()! @#$%^ &*()!")
        assert score < 0.3

    def test_some_garbled(self):
        score = _garbled_ratio("hello @#$%^ world &*()!")
        assert 0.2 < score < 1.0

    def test_markdown_syntax_ignored(self):
        # Markdown tokens like # and - should not count as garbled
        assert _garbled_ratio("# heading text here") == 1.0

    def test_empty(self):
        assert _garbled_ratio("") == 0.0


class TestContentLengthScore:
    def test_empty(self):
        assert _content_length_score("") == 0.0

    def test_very_short(self):
        assert _content_length_score("hi") == 0.1

    def test_short(self):
        assert _content_length_score("This is a short text snippet.") == 0.3

    def test_medium(self):
        text = "word " * 30  # 150 chars
        assert _content_length_score(text) == 0.7

    def test_long(self):
        text = "word " * 200  # 1000 chars
        assert _content_length_score(text) == 1.0


class TestWhitespaceScore:
    def test_no_blanks(self):
        assert _whitespace_score("line one\nline two\nline three") == 1.0

    def test_normal_blanks(self):
        # Some blank lines are normal
        text = "paragraph one\n\nparagraph two\n\nparagraph three"
        assert _whitespace_score(text) >= 0.8

    def test_excessive_blanks(self):
        text = "text\n\n\n\n\n\n\n\n\n\nmore text"
        assert _whitespace_score(text) < 0.6

    def test_mostly_blank(self):
        text = "\n\n\n\n\n\nonly one line\n\n\n\n\n\n\n"
        assert _whitespace_score(text) <= 0.3


class TestStructureScore:
    def test_heading(self):
        text = "# My Heading\n\nSome paragraph text here."
        assert _structure_score(text) >= 0.6

    def test_list(self):
        text = "- item one\n- item two\n- item three"
        assert _structure_score(text) >= 0.6

    def test_table(self):
        text = "| Col1 | Col2 |\n|------|------|\n| a | b |"
        assert _structure_score(text) >= 0.6

    def test_rich_structure(self):
        text = "# Heading\n\n- item one\n- item two\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nParagraph.\n\n"
        assert _structure_score(text) >= 0.8

    def test_no_structure(self):
        text = "just some plain text"
        assert _structure_score(text) < 0.5

    def test_multiple_paragraphs(self):
        text = "First paragraph here.\n\nSecond paragraph here.\n\n"
        assert _structure_score(text) >= 0.6


# --- Overall score tests ---


class TestScoreQuality:
    def test_empty_string(self):
        assert score_quality("") == 0.0

    def test_whitespace_only(self):
        assert score_quality("   \n\n  \t  ") == 0.0

    def test_none_input(self):
        assert score_quality(None) == 0.0

    def test_clean_well_structured_markdown(self):
        text = """# Project Report

## Introduction

This document provides an overview of the project status and deliverables.
The team has been working diligently on multiple fronts.

## Key Findings

- Finding one: performance improved by twenty percent
- Finding two: user satisfaction increased significantly
- Finding three: deployment time was reduced

## Data Summary

| Metric | Value | Change |
|--------|-------|--------|
| Users | 1500 | +20% |
| Revenue | 50000 | +15% |
| Uptime | 99.9 | +0.1% |

## Conclusion

Overall the project has been successful and we recommend continuing
with the current approach for the next quarter.
"""
        score = score_quality(text)
        assert score > 0.8, f"Expected >0.8 for clean markdown, got {score}"

    def test_garbled_ocr_output(self):
        text = "@ #$% ^&* ()! ~`| {}<> @#$ %^& *()"
        score = score_quality(text)
        assert score < 0.4, f"Expected <0.4 for garbled text, got {score}"

    def test_minimal_text(self):
        score = score_quality("No text detected")
        assert score < 0.75, f"Expected <0.75 for minimal text, got {score}"

    def test_normal_paragraph(self):
        text = (
            "The quick brown fox jumps over the lazy dog. "
            "This sentence contains several common English words and demonstrates "
            "that the text extraction worked correctly. The output is readable "
            "and makes logical sense as a coherent paragraph of text that would "
            "be useful as context input for a language model."
        )
        score = score_quality(text)
        assert score > 0.6, f"Expected >0.6 for normal paragraph, got {score}"

    def test_score_range(self):
        """Score should always be between 0.0 and 1.0."""
        test_inputs = [
            "",
            "a",
            "hello world",
            "# heading\n\nparagraph",
            "@#$%^&*()",
            "word " * 1000,
        ]
        for text in test_inputs:
            score = score_quality(text)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for input: {text[:50]}"
