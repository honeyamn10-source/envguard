"""Tests for the builtin detector ruleset."""

import pytest

from envguard.rules import (
    BUILTIN_RULES,
    SEVERITIES,
    SEVERITY_ORDER,
    looks_like_placeholder,
    mask_secret,
    severity_pass,
    validate_severity,
)

EXPECTED_DETECTORS = [
    "aws-access-key-id",
    "aws-secret-access-key",
    "github-pat",
    "slack-token",
    "stripe-key",
    "openai-api-key",
    "private-key",
    "postgresql-url",
    "redis-url",
    "mysql-url",
    "mongodb-url",
    "jwt",
    "high-entropy-hex",
    "high-entropy-base64",
]


def test_builtin_rules_have_expected_detectors():
    assert [rule.name for rule in BUILTIN_RULES] == EXPECTED_DETECTORS


def test_all_rules_have_descriptions_and_patterns():
    for rule in BUILTIN_RULES:
        assert rule.description
        assert rule.pattern


def test_rule_severities_are_valid():
    for rule in BUILTIN_RULES:
        assert rule.severity in SEVERITIES
        assert rule.severity in SEVERITY_ORDER


def test_rule_names_are_unique():
    names = [rule.name for rule in BUILTIN_RULES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    "value",
    [
        "YOUR_API_KEY_HERE",
        "yourkeyhere",
        "my_secret",
        "changeme",
        "changeme123",
        "<put_token_here>",
        "...",
        "xxxx",
        "********",
        "test_secret",
        "example",
        "example123",
        "sample-token",
        "put_key_here",
        "insert your password",
        "replaceme",
    ],
)
def test_placeholder_values_recognised(value):
    assert looks_like_placeholder(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "sk_" + "live_" + "abcd1234abcd1234abcd1234",
        "ghp_1234567890abcdefghijklmnopqrstuvwxyzABCDEF",
        "letmein123",
        "300bbb6dcfea31a3e22a1de84d12d295a51cb0c341de5a410577ac8e5436b475",
        "postgres://user:pw@host/db",
    ],
)
def test_real_looking_values_not_placeholders(value):
    assert looks_like_placeholder(value) is False


def test_empty_string_placeholder():
    assert looks_like_placeholder("") is True


def test_mask_secret_preview():
    assert mask_secret("AKIAIOSFODNN7EXAMPLE") == "AKIA****MPLE"
    assert mask_secret("short") == "****"
    assert mask_secret("") == "****"


def test_validate_severity_accepts_csv():
    assert validate_severity("critical,high") == {"critical", "high"}
    assert validate_severity(" critical , LOW ") == {"critical", "low"}
    assert validate_severity(None) is None


def test_validate_severity_rejects_unknown():
    with pytest.raises(ValueError):
        validate_severity("critical,bogus")


def test_severity_pass():
    assert severity_pass("high", {"high", "critical"}) is True
    assert severity_pass("low", {"high"}) is False
    assert severity_pass("high", None) is True