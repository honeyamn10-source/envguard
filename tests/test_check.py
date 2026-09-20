"""Tests for the ``.env`` linting engine."""

import json

from envguard.check import CheckOptions, lint, lint_texts, parse_env, to_json
from envguard.cli import cli

EXAMPLE = "API_KEY=abc123\nDEBUG=true\n"
ENV_OK = "API_KEY=abc123\nDEBUG=true\n"


def test_pass_when_env_matches_example():
    issues = lint_texts(ENV_OK, EXAMPLE)
    assert issues == []


def test_missing_key_reported():
    issues = lint_texts("DEBUG=true\n", EXAMPLE)
    missing = [issue for issue in issues if issue.code == "missing-key"]
    assert len(missing) == 1
    assert "API_KEY" in missing[0].message
    assert missing[0].severity == "warning"
    assert missing[0].line is None


def test_extra_key_reported():
    issues = lint_texts("API_KEY=abc123\nDEBUG=true\nLOCAL_ONLY=1\n", EXAMPLE)
    extra = [issue for issue in issues if issue.code == "extra-key"]
    assert len(extra) == 1
    assert "LOCAL_ONLY" in extra[0].message
    assert extra[0].severity == "warning"


def test_extra_key_allowlisted():
    issues = lint_texts(
        "API_KEY=abc123\nDEBUG=true\nLOCAL_ONLY=1\n",
        EXAMPLE,
        CheckOptions(allow=["LOCAL_ONLY"]),
    )
    assert [issue.code for issue in issues] == []


def test_duplicate_key_reported():
    issues = lint_texts("DUPE=a\nDUPE=b\n", "DUPE=x\n")
    duplicates = [issue for issue in issues if issue.code == "duplicate-key"]
    assert len(duplicates) == 1
    assert duplicates[0].line == 1
    assert "appears 2 times" in duplicates[0].message


def test_later_duplicate_wins():
    entries = parse_env("DUPE=a\nDUPE=b\n")
    assert entries["DUPE"].value == "b"
    assert entries["DUPE"].line == 2


def test_unquoted_hash_value_reported():
    issues = lint_texts("K=a#b\n", "K=x\n")
    assert any(issue.code == "unquoted-hash" for issue in issues)


def test_unquoted_space_value_reported():
    issues = lint_texts("K=two words\n", "K=x\n")
    assert any(issue.code == "unquoted-space" for issue in issues)


def test_quoted_values_not_reported():
    issues = lint_texts('K="a#b c"\n', "K=x\n")
    assert not any(issue.code.startswith("unquoted") for issue in issues)


def test_empty_required_reported():
    issues = lint_texts("PWD=\n", "PWD=hunter2\n")
    empty = [issue for issue in issues if issue.code == "empty-required"]
    assert len(empty) == 1
    assert empty[0].severity == "error"
    assert empty[0].line == 1


def test_optional_key_can_be_empty():
    issues = lint_texts("OPT=\n", "OPT=\n")
    assert [issue.code for issue in issues] == []


def test_require_flag_forces_required():
    issues = lint_texts("OPT=\n", "OPT=\n", CheckOptions(require=["OPT"]))
    assert any(issue.code == "empty-required" for issue in issues)


def test_require_flag_missing_key_is_reported():
    issues = lint_texts("OTHER=1\n", "OPT=\n", CheckOptions(require=["OPT"]))
    assert any(issue.code in ("missing-key", "empty-required") for issue in issues)


def test_malformed_line_reported():
    issues = lint_texts("just_some_text\n", EXAMPLE)
    malformed = [issue for issue in issues if issue.code == "malformed-line"]
    assert len(malformed) == 1
    assert malformed[0].severity == "error"


def test_invalid_key_name_reported():
    issues = lint_texts("BAD KEY=x\n", EXAMPLE)
    malformed = [issue for issue in issues if issue.code == "malformed-line"]
    assert len(malformed) == 1
    assert "BAD KEY" in malformed[0].message


def test_commented_key_reported():
    issues = lint_texts("# DISABLED_FEATURE=1\n", EXAMPLE)
    commented = [issue for issue in issues if issue.code == "commented-key"]
    assert len(commented) == 1
    assert "DISABLED_FEATURE" in commented[0].message


def test_export_prefix_parsed():
    issues = lint_texts("export API_KEY=abc123\nexport DEBUG=true\n", EXAMPLE)
    assert issues == []


def test_strict_upgrades_warnings_to_errors():
    issues = lint_texts("API_KEY=abc123\nDEBUG=true\nLOCAL_ONLY=1\n", EXAMPLE, CheckOptions(strict=True))
    assert issues
    assert all(issue.severity == "error" for issue in issues)


def test_strict_keeps_errors_as_errors():
    issues = lint_texts("PWD=\nLOCAL_ONLY=1\n", "PWD=x\n", CheckOptions(strict=True))
    codes = {issue.code for issue in issues}
    assert "empty-required" in codes and "extra-key" in codes
    assert all(issue.severity == "error" for issue in issues)


def test_json_output_schema(tmp_path, make_tree, capsys):
    root = make_tree(
        tmp_path,
        {
            ".env": "MISSING_HERE=\nLOCAL_ONLY=1\n",
            ".env.example": "REQUIRED_SERVICE=set-me\nOTHER_FIELD=ok\n",
        },
    )
    code = cli(["check", str(root), "--json"])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["command"] == "check"
    assert data["ok"] is False
    assert data["env"] == str(root / ".env")
    assert isinstance(data["issues"], list)
    assert isinstance(data["keys"], list)


def test_lint_filesystem_and_to_json(tmp_path, make_tree):
    root = make_tree(
        tmp_path,
        {
            ".env": "HAS_SECRET=123\nA_SECOND=1\n",
            ".env.example": "REQUIRED_SERVICE=set-me\n",
        },
    )
    result = lint(root / ".env", root / ".env.example")
    assert not result.ok
    payload = to_json(result)
    assert payload["command"] == "check"
    assert payload["ok"] is False
    assert isinstance(payload["issues"], list)
    assert isinstance(payload["counts"], dict)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "missing-key" in codes and "extra-key" in codes and "empty-required" not in codes
    for issue in payload["issues"]:
        assert set(issue.keys()) == {"code", "line", "severity", "message"}


def test_fixture_expected_issues(fixtures):
    result = lint(fixtures / "sample.env", fixtures / "sample.env.example")
    assert not result.ok
    assert len(result.issues) == 11
    assert result.warnings == 9
    assert result.errors == 2
    codes = sorted({issue.code for issue in result.issues})
    assert codes == [
        "commented-key",
        "duplicate-key",
        "extra-key",
        "malformed-line",
        "missing-key",
        "unquoted-hash",
        "unquoted-space",
    ]


def test_check_exit_code_zero(tmp_path, make_tree):
    root = make_tree(tmp_path, {"env.txt": "A=b\n", "example.txt": "A=b\n"})
    assert cli(["check", str(root / "env.txt"), "--example", str(root / "example.txt")]) == 0


def test_check_exit_code_one(tmp_path, make_tree):
    root = make_tree(tmp_path, {"env.txt": "A=\n", "example.txt": "A=b\n"})
    assert cli(["check", str(root / "env.txt"), "--example", str(root / "example.txt")]) == 1


def test_check_missing_example_exits_two(tmp_path, make_tree):
    root = make_tree(tmp_path, {"env.txt": "A=b\n"})
    assert cli(["check", str(root / "env.txt")]) == 2


def test_check_missing_env_exits_two(tmp_path):
    assert cli(["check", str(tmp_path)]) == 2


def test_check_nonexistent_path_exits_two(tmp_path):
    assert cli(["check", str(tmp_path / "nope")]) == 2


def test_check_report_human_fields(tmp_path, make_tree, capsys):
    root = make_tree(tmp_path, {"env.txt": "A=b\n", "example.txt": "B=c\n"})
    assert cli(["check", str(root / "env.txt"), "--example", str(root / "example.txt")]) == 1
    out = capsys.readouterr().out
    assert "env.txt:" in out
    assert "missing-key" in out
    assert "Summary:" in out