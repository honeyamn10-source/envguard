"""Tests for gitignore and ``.envguard-ignore`` parsing."""

from envguard.ignore import (
    BUILTIN_IGNORE_PATTERNS,
    IgnoreMatcher,
    is_suppressed,
    parse_envguard_ignore,
)


def build(patterns):
    """Create a matcher from a list of raw pattern lines."""
    matcher = IgnoreMatcher()
    matcher.add(patterns)
    return matcher


def test_builtin_ignore_list_has_common_vendors():
    joined = "\n".join(BUILTIN_IGNORE_PATTERNS)
    assert ".git/" in joined
    assert "node_modules/" in joined
    assert "__pycache__/" in joined
    assert "package-lock.json" in joined
    assert "*.lock" in joined


def test_dir_pattern_ignores_contents():
    matcher = build(["cache/"])
    assert matcher.is_ignored("cache/x.txt")
    assert matcher.is_ignored("cache", is_dir=True)
    assert matcher.is_ignored("src/cache/x.txt")
    assert not matcher.is_ignored("cached.txt")
    assert not matcher.is_ignored("src/app.py")


def test_anchored_pattern_only_root():
    matcher = build(["/notes.txt"])
    assert matcher.is_ignored("notes.txt")
    assert not matcher.is_ignored("docs/notes.txt")


def test_extension_pattern_matches_anywhere():
    matcher = build(["*.log"])
    assert matcher.is_ignored("app.log")
    assert matcher.is_ignored("src/debug.log")
    assert not matcher.is_ignored("app.logs")
    assert not matcher.is_ignored("app.py")


def test_plain_pattern_matches_any_component():
    matcher = build(["build"])
    assert matcher.is_ignored("build")
    assert matcher.is_ignored("out/build/x.txt")
    assert matcher.is_ignored("x/build")
    assert not matcher.is_ignored("building.py")


def test_negation_last_match_wins():
    matcher = build(["*.log", "!keep.log"])
    assert matcher.is_ignored("app.log")
    assert not matcher.is_ignored("keep.log")


def test_comments_and_blank_lines_skipped():
    matcher = build(["# comment", "", "  ", "*.tmp"])
    assert matcher.is_ignored("a.tmp")
    assert not matcher.is_ignored("a.py")


def test_nested_base_scoping():
    matcher = IgnoreMatcher()
    matcher.add(["generated.txt"], base="src")
    assert matcher.is_ignored("src/generated.txt")
    assert not matcher.is_ignored("generated.txt")
    assert not matcher.is_ignored("other/generated.txt")


def test_root_base_applies_everywhere():
    matcher = IgnoreMatcher()
    matcher.add(["secret.txt"], base="")
    assert matcher.is_ignored("secret.txt")
    assert matcher.is_ignored("deep/nested/secret.txt")


def test_edge_patterns_match_basename_of_anchored():
    matcher = build(["/dist/_.html"])
    assert matcher.is_ignored("dist/_.html")
    assert not matcher.is_ignored("a/dist/_.html")


def test_parse_envguard_ignore_basic():
    rules = parse_envguard_ignore("# comment\n*.pem\nconfig/local.env:mongodb-url\n")
    assert len(rules) == 2
    assert rules[0].glob == "*.pem"
    assert rules[0].detector is None
    assert rules[1].glob == "config/local.env"
    assert rules[1].detector == "mongodb-url"


def test_envguard_ignore_blank_lines_skipped():
    rules = parse_envguard_ignore("\n\n\n")
    assert rules == []


def test_is_suppressed_whole_file():
    rules = parse_envguard_ignore("*.pem\n")
    assert is_suppressed("keys/secret.pem", "private-key", rules)
    assert is_suppressed("keys/secret.pem", "any-detector", rules)
    assert not is_suppressed("config.py", "private-key", rules)


def test_is_suppressed_detector_scoped():
    rules = parse_envguard_ignore("config/local.env:mongodb-url\n")
    assert is_suppressed("config/local.env", "mongodb-url", rules)
    assert not is_suppressed("config/local.env", "aws-access-key-id", rules)
    assert not is_suppressed("other/local.env", "mongodb-url", rules)


def test_is_suppressed_globbing_without_path():
    rules = parse_envguard_ignore("local.env:mongodb-url\n")
    assert is_suppressed("deep/nested/local.env", "mongodb-url", rules)


def test_is_suppressed_star_detector():
    rules = parse_envguard_ignore("scratch/*:*\n")
    assert is_suppressed("scratch/a.txt", "jwt", rules)
    assert not is_suppressed("app/a.txt", "jwt", rules)