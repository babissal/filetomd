"""Quality scoring for converted Markdown output."""

import re


def score_quality(markdown: str) -> float:
    """Score the quality of converted Markdown text.

    Returns a score from 0.0 (garbled/empty) to 1.0 (excellent).
    The score is a weighted average of format-agnostic heuristics.

    Args:
        markdown: The converted Markdown string to evaluate.

    Returns:
        Quality score between 0.0 and 1.0.
    """
    if not markdown or not markdown.strip():
        return 0.0

    scores = [
        (_word_density(markdown), 0.25),
        (_garbled_ratio(markdown), 0.25),
        (_content_length_score(markdown), 0.20),
        (_whitespace_score(markdown), 0.15),
        (_structure_score(markdown), 0.15),
    ]

    return sum(score * weight for score, weight in scores)


def _word_density(markdown: str) -> float:
    """Ratio of dictionary-like words to total tokens.

    Dictionary-like = alphabetic, length >= 2.
    Low ratio suggests garbled OCR output.
    """
    tokens = markdown.split()
    if not tokens:
        return 0.0

    word_count = sum(1 for t in tokens if t.isalpha() and len(t) >= 2)
    return word_count / len(tokens)


def _garbled_ratio(markdown: str) -> float:
    """Score based on absence of garbled tokens.

    Returns 1.0 when no garbled tokens exist, 0.0 when all tokens are garbled.
    Garbled = excessive punctuation, non-ASCII runs, isolated single characters.
    """
    tokens = markdown.split()
    if not tokens:
        return 0.0

    garbled = 0
    for token in tokens:
        # Skip Markdown syntax tokens
        if token in ("#", "##", "###", "####", "#####", "######",
                      "-", "*", ">", "---", "***", "|", "```"):
            continue

        # Excessive punctuation (more than half the chars are non-alphanumeric)
        alpha_count = sum(1 for c in token if c.isalnum())
        if len(token) >= 3 and alpha_count < len(token) * 0.4:
            garbled += 1
            continue

        # Non-ASCII runs (3+ consecutive non-ASCII characters, excluding common Unicode)
        if re.search(r'[^\x00-\x7f]{3,}', token):
            # Allow common accented characters but flag truly garbled sequences
            stripped = re.sub(r'[\u00c0-\u024f]', '', token)  # Remove Latin Extended
            if re.search(r'[^\x00-\x7f]{3,}', stripped):
                garbled += 1
                continue

    ratio = garbled / len(tokens)
    return max(0.0, 1.0 - ratio * 1.5)  # Penalise: 67% garbled = 0 score


def _content_length_score(markdown: str) -> float:
    """Score based on content length.

    Very short output likely indicates failed extraction.
    """
    length = len(markdown.strip())

    if length == 0:
        return 0.0
    if length < 20:
        return 0.1
    if length < 50:
        return 0.3
    if length < 100:
        return 0.5
    if length < 200:
        return 0.7
    if length < 500:
        return 0.85
    return 1.0


def _whitespace_score(markdown: str) -> float:
    """Score based on whitespace ratio.

    Excessive blank lines suggest extraction issues.
    """
    lines = markdown.split('\n')
    if not lines:
        return 0.0

    blank_count = sum(1 for line in lines if not line.strip())
    total = len(lines)
    blank_ratio = blank_count / total

    # Some blank lines are normal in Markdown (between paragraphs, etc.)
    # Penalise when more than ~40% of lines are blank
    if blank_ratio <= 0.3:
        return 1.0
    if blank_ratio <= 0.5:
        return 0.8
    if blank_ratio <= 0.7:
        return 0.5
    return 0.2


def _structure_score(markdown: str) -> float:
    """Score based on presence of Markdown structure.

    Well-structured output with headings, lists, tables scores higher.
    """
    score = 0.0
    indicators_found = 0

    # Headings
    if re.search(r'^#{1,6}\s+\S', markdown, re.MULTILINE):
        indicators_found += 1

    # Lists (bullet or numbered)
    if re.search(r'^[\s]*[-*+]\s+\S', markdown, re.MULTILINE):
        indicators_found += 1

    # Numbered lists
    if re.search(r'^[\s]*\d+\.\s+\S', markdown, re.MULTILINE):
        indicators_found += 1

    # Tables
    if re.search(r'\|.*\|', markdown):
        indicators_found += 1

    # Paragraphs (blocks of text separated by blank lines)
    paragraphs = re.findall(r'\S[\s\S]*?\n\n', markdown)
    if len(paragraphs) >= 2:
        indicators_found += 1

    # Score: having at least some structure is good
    if indicators_found == 0:
        # Plain text with no structure — still okay if it has content
        lines = [l for l in markdown.split('\n') if l.strip()]
        score = 0.4 if len(lines) >= 3 else 0.2
    elif indicators_found == 1:
        score = 0.6
    elif indicators_found == 2:
        score = 0.8
    else:
        score = 1.0

    return score
