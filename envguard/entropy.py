"""Shannon entropy helpers used by the high-entropy secret detectors."""

import math
import re
from typing import Dict

HEX_POOL_SIZE = 16
BASE64_POOL_SIZE = 64

HEX_MIN_LENGTH = 32
BASE64_MIN_LENGTH = 32

_HEX_TOKEN_RE = re.compile(r"^(?:[0-9a-fA-F]{32,})$")
_BASE64_TOKEN_RE = re.compile(r"^(?:[A-Za-z0-9+/]{32,})$")

_HEX_ENTROPY_THRESHOLD = 2.5
_BASE64_ENTROPY_THRESHOLD = 3.0

_HEX_SCORE_THRESHOLD = 20.0
_BASE64_SCORE_THRESHOLD = 25.0


def shannon_entropy(text: str) -> float:
    """Compute the Shannon entropy of a string in bits per symbol.

    Args:
        text: The string to analyse.

    Returns:
        Shannon entropy in bits per symbol, or ``0.0`` for empty input.
    """
    if not text:
        return 0.0
    total = len(text)
    counts: Dict[str, int] = {}
    for char in text:
        counts[char] = counts.get(char, 0) + 1
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def weighted_shannon_entropy(text: str, pool_size: int) -> float:
    """Compute a length-weighted Shannon entropy score for a token.

    The raw Shannon entropy (bits per symbol) is normalised against the
    maximum possible entropy for the given alphabet ``pool_size`` and then
    multiplied by the token length, so longer, diversified strings score
    higher than short or repetitive ones.

    Args:
        text: The token to score.
        pool_size: Size of the alphabet the token is drawn from.

    Returns:
        A score in the range ``[0.0, len(text)]``.
    """
    if not text or pool_size < 2:
        return 0.0
    entropy = shannon_entropy(text)
    max_entropy = math.log2(pool_size)
    normalized = min(entropy / max_entropy, 1.0)
    return round(normalized * len(text), 6)


def is_high_entropy(token: str, kind: str) -> bool:
    """Decide whether a token looks like a randomly generated secret.

    Applies a length floor, a character-class check and two independent
    entropy gates (raw Shannon entropy and the weighted score) so that
    short, repetitive or dictionary-like strings are never flagged.

    Args:
        token: The candidate secret value.
        kind: Either ``"hex"`` or ``"base64"``.

    Returns:
        ``True`` when the token passes every heuristic gate.
    """
    candidate = token.strip()
    if kind == "hex":
        if len(candidate) < HEX_MIN_LENGTH or not _HEX_TOKEN_RE.match(candidate):
            return False
        return (
            shannon_entropy(candidate) >= _HEX_ENTROPY_THRESHOLD
            and weighted_shannon_entropy(candidate, HEX_POOL_SIZE) >= _HEX_SCORE_THRESHOLD
        )
    if kind == "base64":
        candidate = candidate.rstrip("=")
        if len(candidate) < BASE64_MIN_LENGTH or not _BASE64_TOKEN_RE.match(candidate):
            return False
        if _HEX_TOKEN_RE.match(candidate):
            return False
        return (
            shannon_entropy(candidate) >= _BASE64_ENTROPY_THRESHOLD
            and weighted_shannon_entropy(candidate, BASE64_POOL_SIZE) >= _BASE64_SCORE_THRESHOLD
        )
    return False