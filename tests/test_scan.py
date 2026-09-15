"""Tests for the secret scanning engine."""

import json

import pytest

from envguard.cli import cli
from envguard.rules import BUILTIN_RULES, looks_like_placeholder
from envguard.scan import Finding, ScanError, scan_path

HEX_SECRET = "300bbb6dcfea31a3e22a1de84d12d295a51cb0c341de5a410577ac8e5436b475"
B64_SECRET = "piA8CnkArR2YjzO1QxfeQODGz0idDvgywiN8bVGQeY/o0lYa"
AWS_ACCESS = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
GITHUB_PAT = "ghp_1234567890abcdefghijklmnopqrstuvwxyzABCDEF"
GITHUB_PAT_NEW = "github_pat_11AAA4444B5Q1nQhxYYX_iZe0abc12DEF456ghi"


def _slack_token():
    return "xox" "b-1234567890" + "-1234567890-" + "abcdefghijklmnop"


def _stripe_key():
    return "sk_" "live_" + "abcd1234abcd1234abcd1234"
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWV9."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


def scan_env(make_tree, tmp_path, content, name="config.env", root=None, **kwargs):
    """Scan a single-file tree and return the findings."""
    if root is None:
        root = make_tree(tmp_path, {name: content})
    return scan_path(root, **kwargs)


def detectors(result):
    """Return the set of detector names found."""
    return {finding.detector for finding in result.findings}


def test_finds_aws_access_key(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n")
    finding = result.findings[0]
    assert finding.detector == "aws-access-key-id"
    assert finding.severity == "critical"
    assert finding.line == 1
    assert finding.secret == "AKIA****MPLE"


def test_finds_aws_secret_key(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, f"AWS_SECRET_ACCESS_KEY={AWS_SECRET}\n")
    finding = result.findings[0]
    assert finding.detector == "aws-secret-access-key"
    assert finding.severity == "critical"
    assert finding.line == 1


def test_finds_github_pat(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, f"GITHUB_TOKEN={GITHUB_PAT}\n")
    finding = result.findings[0]
    assert finding.detector == "github-pat"
    assert finding.severity == "high"
    assert finding.line == 1


def test_finds_github_pat_new_format(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, f"GH_TOKEN={GITHUB_PAT_NEW}\n")
    assert result.findings
    assert result.findings[0].detector == "github-pat"


def test_finds_slack_token(make_tree, tmp_path):
    slack = _slack_token()
    result = scan_env(make_tree, tmp_path, "SLACK={}\n".format(slack))
    assert result.findings[0].detector == "slack-token"
    assert result.findings[0].severity == "high"


def test_finds_stripe_key(make_tree, tmp_path):
    stripe = _stripe_key()
    result = scan_env(make_tree, tmp_path, "STRIPE_KEY={}\n".format(stripe))
    assert result.findings[0].detector == "stripe-key"
    assert result.findings[0].severity == "critical"


def test_finds_openai_key(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, "OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuv\n")
    assert result.findings[0].detector == "openai-api-key"
    assert result.findings[0].severity == "high"


def test_finds_private_key(make_tree, tmp_path):
    content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA4BnPZ8bNlqGt9KaCJ4B2+Cb1UK4o5J3y8F2GkvKg==\n-----END RSA PRIVATE KEY-----\n"
    result = scan_env(make_tree, tmp_path, content)
    assert result.findings[0].detector == "private-key"
    assert result.findings[0].severity == "critical"
    assert result.findings[0].line == 1


def test_finds_openssh_private_key(make_tree, tmp_path):
    content = "-----BEGIN OPENSSH PRIVATE KEY-----\nabcdef\n-----END OPENSSH PRIVATE KEY-----\n"
    assert scan_env(make_tree, tmp_path, content).findings[0].detector == "private-key"


def test_finds_connection_strings(make_tree, tmp_path):
    content = "\n".join(
        [
            "PG=postgres://user:pw@host/db",
            "REDIS=redis://user:pw@host:6379",
            "MYSQL=mysql://user:pw@host/db",
            "MONGO=mongodb://user:pw@host/db",
            "MONGO_SRV=mongodb+srv://user:pw@host/db",
        ]
    ) + "\n"
    result = scan_env(make_tree, tmp_path, content)
    found = detectors(result)
    assert {"postgresql-url", "redis-url", "mysql-url", "mongodb-url"} <= found


def test_passwordless_urls_not_flagged(make_tree, tmp_path):
    content = "PG=postgres://localhost:5432/app\nREDIS=redis://localhost:6379\n"
    result = scan_env(make_tree, tmp_path, content)
    assert detectors(result) == set()


def test_finds_jwt(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, f"TOKEN={JWT}\n")
    assert result.findings[0].detector == "jwt"
    assert result.findings[0].severity == "high"


def test_finds_high_entropy_hex(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, f"API_SECRET={HEX_SECRET}\n")
    assert result.findings[0].detector == "high-entropy-hex"
    assert result.findings[0].severity == "medium"


def test_finds_high_entropy_base64(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, f"CLIENT_TOKEN={B64_SECRET}\n")
    assert result.findings[0].detector == "high-entropy-base64"
    assert result.findings[0].severity == "medium"


def test_plain_password_not_flagged(make_tree, tmp_path):
    result = scan_env(make_tree, tmp_path, "PASSWORD=letmein123\n")
    assert detectors(result) == set()


def test_placeholders_not_flagged(make_tree, tmp_path):
    contents = [
        "API_KEY=YOUR_API_KEY_HERE\n",
        "API_KEY=<put_token_here>\n",
        "API_KEY=changeme\n",
        "API_KEY=xxxx\n",
        "API_KEY=test_secret\n",
    ]
    root = make_tree(
        tmp_path,
        {f"f{i}.env": content for i, content in enumerate(contents)},
    )
    result = scan_path(root)
    assert result.findings == []


def test_severity_filter(make_tree, tmp_path):
    content = f"API_SECRET={HEX_SECRET}\nAWS_ACCESS_KEY_ID={AWS_ACCESS}\n"
    root = make_tree(tmp_path, {"config.env": content})
    medium_only = scan_path(root, severity={"medium"})
    assert {finding.detector for finding in medium_only.findings} == {"high-entropy-hex"}
    critical_high = scan_path(root, severity={"critical", "high"})
    assert {finding.detector for finding in critical_high.findings} == {"aws-access-key-id"}


def test_max_findings_stops_early(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            "a1.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "b2.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "c3.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
        },
    )
    result = scan_path(root, max_findings=2)
    assert len(result.findings) == 2
    assert result.truncated is True


def test_gitignore_excludes_files(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            ".gitignore": "wip/\n*.secret\n",
            "wip/leak.txt": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "data.secret": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "config.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
        },
    )
    result = scan_path(root)
    assert len(result.findings) == 1
    assert result.findings[0].path == "config.env"


def test_gitignore_negation_unignores(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            ".gitignore": "*.log\n!important.log\n",
            "app.log": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "important.log": f"TOKEN={GITHUB_PAT}\n",
        },
    )
    result = scan_path(root)
    assert [finding.path for finding in result.findings] == ["important.log"]
    assert result.findings[0].detector == "github-pat"


def test_nested_gitignore_applies(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            ".gitignore": "root_ignore.txt\n",
            "root_ignore.txt": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "src/.gitignore": "deep.secret\n",
            "src/deep.secret": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "src/app.py": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
        },
    )
    result = scan_path(root)
    assert [finding.path for finding in result.findings] == ["src/app.py"]


def test_git_info_exclude_honoured(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            ".git/info/exclude": "excluded.txt\n",
            "excluded.txt": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "kept.txt": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
        },
    )
    result = scan_path(root)
    assert [finding.path for finding in result.findings] == ["kept.txt"]


def test_builtin_ignores_prune_vendors(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            "node_modules/pkg/index.js": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            ".venv/lib/site.py": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "src/app.py": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
        },
    )
    result = scan_path(root)
    assert [finding.path for finding in result.findings] == ["src/app.py"]


def test_envguard_ignore_file(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            ".envguard-ignore": "*.pem\nconfig/local.env:mongodb-url\n",
            "key.pem": "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n",
            "config/local.env": (
                f"MONGO=mongodb://user:pw@host/db\nAWS_ACCESS_KEY_ID={AWS_ACCESS}\n"
            ),
        },
    )
    result = scan_path(root)
    paths = {(finding.path, finding.detector) for finding in result.findings}
    assert paths == {("config/local.env", "aws-access-key-id")}


def test_binary_file_skipped(make_tree, tmp_path):
    root = make_tree(tmp_path, {"data.bin": "placeholder"})
    (root / "data.bin").write_bytes(b"AWS_ACCESS_KEY_ID=" + AWS_ACCESS.encode() + b"\x00\xff\xfe")
    result = scan_path(root)
    assert result.findings == []
    assert result.files_scanned == 0


def test_large_file_skipped(make_tree, tmp_path):
    root = make_tree(tmp_path, {"big.txt": "pad"})
    with open(root / "big.txt", "w") as handle:
        handle.write(f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n")
        handle.write("x" * (1_100_000))
    result = scan_path(root)
    assert result.findings == []
    assert result.files_skipped == 1


def test_fixture_tree_findings(scanner_fixture):
    result = scan_path(scanner_fixture)
    found = {(finding.path, finding.line, finding.detector) for finding in result.findings}
    expected = {
        ("config/settings.env", 2, "aws-access-key-id"),
        ("config/settings.env", 3, "aws-secret-access-key"),
        ("config/settings.env", 4, "github-pat"),
        ("config/settings.env", 5, "slack-token"),
        ("config/settings.env", 6, "stripe-key"),
        ("config/settings.env", 7, "openai-api-key"),
        ("config/settings.env", 8, "mysql-url"),
        ("config/settings.env", 9, "mongodb-url"),
        ("config/settings.env", 10, "postgresql-url"),
        ("config/settings.env", 11, "redis-url"),
        ("config/settings.env", 12, "jwt"),
        ("config/settings.env", 15, "high-entropy-hex"),
        ("config/settings.env", 16, "high-entropy-base64"),
        ("keys/test_key.pem", 1, "private-key"),
    }
    assert found == expected
    assert not result.ok


def test_scan_single_file(make_tree, tmp_path):
    root = make_tree(tmp_path, {"one.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n"})
    result = scan_path(root / "one.env")
    assert len(result.findings) == 1
    assert result.findings[0].path == "one.env"


def test_scan_missing_path_exits_two(tmp_path):
    with pytest.raises(ScanError):
        scan_path(tmp_path / "missing")


def test_scan_cli_exit_codes(make_tree, tmp_path):
    planted = make_tree(tmp_path, {"config.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n"})
    assert cli(["scan", str(planted)]) == 1
    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    clean = make_tree(clean_root, {"clean.txt": "nothing\n"})
    assert cli(["scan", str(clean)]) == 0
    assert cli(["scan", str(tmp_path / "nope")]) == 2


def test_scan_cli_json_format(make_tree, tmp_path, capsys):
    planted = make_tree(tmp_path, {"config.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n"})
    assert cli(["scan", str(planted), "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["command"] == "scan"
    assert data["files_scanned"] >= 1
    assert data["truncated"] is False
    finding = data["findings"][0]
    assert set(finding.keys()) == {"path", "line", "severity", "detector", "description", "secret"}
    assert finding["detector"] == "aws-access-key-id"
    assert "critical" in data["summary"]["by_severity"]


def test_scan_cli_severity_filter(make_tree, tmp_path):
    planted = make_tree(
        tmp_path,
        {"config.env": f"API_SECRET={HEX_SECRET}\nAWS_ACCESS_KEY_ID={AWS_ACCESS}\n"},
    )
    assert cli(["scan", str(planted), "--severity", "medium"]) == 1
    assert cli(["scan", str(planted), "--severity", "critical,high"]) == 1


def test_scan_cli_max_findings(make_tree, tmp_path):
    root = make_tree(
        tmp_path,
        {
            "a.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "b.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
            "c.env": f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n",
        },
    )
    assert cli(["scan", str(root), "--max-findings", "2"]) == 1


def test_all_rules_can_match_at_least_once():
    assert len(BUILTIN_RULES) == 14
    assert looks_like_placeholder("YOUR_API_KEY_HERE") is True


def test_scan_finding_line_number_precision(make_tree, tmp_path):
    content = "line one\nMAIN_TOKEN={}\nline three\n".format(_slack_token())
    result = scan_env(make_tree, tmp_path, content)
    assert {finding.line for finding in result.findings} == {2}