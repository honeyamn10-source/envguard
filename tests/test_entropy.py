"""Tests for the entropy heuristics."""

import base64
import os
import secrets

from envguard.entropy import (
    is_high_entropy,
    shannon_entropy,
    weighted_shannon_entropy,
)


def test_shannon_entropy_empty_returns_zero():
    assert shannon_entropy("") == 0.0


def test_shannon_entropy_uniform_hex():
    alphabet = "0123456789abcdef"
    assert shannon_entropy(alphabet) == 4.0


def test_shannon_entropy_repeating_chars_low():
    assert shannon_entropy("a" * 40) == 0.0


def test_weighted_score_bounds():
    score = weighted_shannon_entropy("deadbeef" * 4, 16)
    assert 0.0 <= score <= len("deadbeef" * 4)
    assert weighted_shannon_entropy("", 16) == 0.0


def test_hex_entropy_accepts_random_token():
    token = secrets.token_hex(32)
    assert is_high_entropy(token, "hex") is True


def test_hex_entropy_rejects_repeated_token():
    assert is_high_entropy("a" * 40, "hex") is False
    assert is_high_entropy("abc" * 12, "hex") is False


def test_hex_entropy_rejects_short_token():
    assert is_high_entropy("0123456789abcdef01234567", "hex") is False


def test_hex_entropy_rejects_non_hex_chars():
    assert is_high_entropy("zz" + "0" * 38, "hex") is False


def test_base64_entropy_accepts_random_token():
    token = base64.b64encode(os.urandom(36)).decode()
    assert is_high_entropy(token, "base64") is True


def test_base64_entropy_rejects_low_diversity():
    assert is_high_entropy("A" * 40, "base64") is False
    assert is_high_entropy("QUFB" * 10, "base64") is False
    assert is_high_entropy("abcabcabc" * 4, "base64") is False


def test_pure_hex_token_is_not_base64():
    token = "300bbb6dcfea31a3e22a1de84d12d295a51cb0c341de5a410577ac8e5436b475"
    assert is_high_entropy(token, "base64") is False
    assert is_high_entropy(token, "hex") is True


def test_unknown_kind_returns_false():
    assert is_high_entropy("abc", "rot13") is False