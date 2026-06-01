"""Lightweight Chinese-friendly string similarity.

Uses character bigrams + Jaccard. No external deps (no jieba, no embeddings).
Works well for short news headlines where word-segmentation noise often hurts
more than it helps.

Examples:
    >>> sim("黄仁勋很孤独", "黄仁勋谈孤独")
    0.71...
    >>> sim("汶川地震18周年", "汶川地震纪念十八周年")
    0.50...
    >>> sim("法式洋娃娃妆", "国际护士节")
    0.0
"""

from __future__ import annotations

import re


def normalize(text: str) -> str:
    """Strip punctuation/whitespace, lowercase ASCII."""
    return re.sub(r"[\s\W_]+", "", text or "", flags=re.UNICODE).lower()


def char_bigrams(text: str) -> set[str]:
    """Return the set of character bigrams in `text` (post-normalize)."""
    s = normalize(text)
    if len(s) < 2:
        # Fallback: treat each char as a "unigram"
        return set(s)
    return {s[i : i + 2] for i in range(len(s) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets. Returns 0 if both empty."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def sim(s1: str, s2: str) -> float:
    """Convenience: similarity between two raw strings."""
    return jaccard(char_bigrams(s1), char_bigrams(s2))
