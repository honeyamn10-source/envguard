"""Tests for the command-line wiring and exit codes."""

from envguard import __version__
from envguard.cli import cli, main

HEX_SECRET = "300bbb6dcfea31a3e22a1de84d12d295a51cb0c341de5a410577ac8e5436b475"
AWS_ACCESS = "AKIAIOSFODNN7EXAMPLE"


def test_no_args_prints_help_and_exits_zero(capsys):
    assert cli([]) == 0
    out = capsys.readouterr().out
    assert "envguard" in out
    assert "check" in out
    assert "scan" in out


def test_root_help_exits_zero(capsys):
    assert cli(["--help"]) == 0
    assert "envguard" in capsys.readouterr().out


def test_check_help_exits_zero(capsys):
    assert cli(["check", "--help"]) == 0
    assert "--example" in capsys.readouterr().out


def test_scan_help_exits_zero(capsys):
    assert cli(["scan", "--help"]) == 0
    assert "--severity" in capsys.readouterr().out


def test_version_flag(capsys):
    assert cli(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_version_matches_module():
    import envguard

    assert __version__ == envguard.__version__


def test_unknown_command_exits_two(capsys):
    assert cli(["frobnicate"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_unknown_flag_exits_two():
    assert cli(["scan", "--nope"]) == 2


def test_invalid_severity_exits_two(capsys):
    assert cli(["scan", "--severity", "bogus"]) == 2
    assert "severity" in capsys.readouterr().err


def test_zero_max_findings_exits_two():
    assert cli(["scan", "--max-findings", "0"]) == 2


def test_scan_missing_path_exits_two(capsys):
    assert cli(["scan", "/definitely/not/here"]) == 2
    assert "error" in capsys.readouterr().err


def test_main_returns_integer():
    result = main()
    assert isinstance(result, int)


def test_check_detects_and_exits_one(tmp_path):
    (tmp_path / "env.txt").write_text("A=\n")
    (tmp_path / "example.txt").write_text("A=b\n")
    assert cli(["check", str(tmp_path / "env.txt"), "--example", str(tmp_path / "example.txt")]) == 1


def test_check_pass_exits_zero(tmp_path):
    (tmp_path / "env.txt").write_text("A=b\n")
    (tmp_path / "example.txt").write_text("A=b\n")
    assert cli(["check", str(tmp_path / "env.txt"), "--example", str(tmp_path / "example.txt")]) == 0


def test_strict_still_exits_one(tmp_path):
    (tmp_path / "env.txt").write_text("LOCAL_ONLY=1\nA=b\n")
    (tmp_path / "example.txt").write_text("A=b\n")
    assert cli(["check", str(tmp_path / "env.txt"), "--example", str(tmp_path / "example.txt"), "--strict"]) == 1


def test_scan_exit_codes(tmp_path, capsys):
    (tmp_path / "config.env").write_text(f"AWS_ACCESS_KEY_ID={AWS_ACCESS}\n")
    assert cli(["scan", str(tmp_path)]) == 1
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.txt").write_text("plain text\n")
    assert cli(["scan", str(clean)]) == 0


def test_scan_json_output_valid(tmp_path, capsys):
    (tmp_path / "config.env").write_text(f"API_SECRET={HEX_SECRET}\n")
    assert cli(["scan", str(tmp_path), "--format", "json"]) == 1
    out = capsys.readouterr().out
    assert '"command": "scan"' in out
    assert '"findings":' in out
    assert '"high-entropy-hex"' in out


def test_check_json_output_valid(tmp_path, capsys):
    (tmp_path / "env.txt").write_text("A=\n")
    (tmp_path / "example.txt").write_text("A=b\n")
    assert cli(["check", str(tmp_path / "env.txt"), "--example", str(tmp_path / "example.txt"), "--json"]) == 1
    out = capsys.readouterr().out
    assert '"command": "check"' in out
    assert '"empty-required"' in out


def test_allow_flag_used(tmp_path):
    (tmp_path / "env.txt").write_text("A=b\nEXTRA=1\n")
    (tmp_path / "example.txt").write_text("A=b\n")
    assert cli(["check", str(tmp_path / "env.txt"), "--example", str(tmp_path / "example.txt")]) == 1
    assert (
        cli(
            [
                "check",
                str(tmp_path / "env.txt"),
                "--example",
                str(tmp_path / "example.txt"),
                "--allow",
                "EXTRA",
            ]
        )
        == 0
    )


def test_require_flag_used(tmp_path):
    (tmp_path / "env.txt").write_text("A=b\n")
    (tmp_path / "example.txt").write_text("A=b\n")
    assert cli(["check", str(tmp_path / "env.txt"), "--example", str(tmp_path / "example.txt")]) == 0
    assert (
        cli(
            [
                "check",
                str(tmp_path / "env.txt"),
                "--example",
                str(tmp_path / "example.txt"),
                "--require",
                "NEEDED",
            ]
        )
        == 1
    )


def test_check_infers_example_from_env_stem(tmp_path):
    (tmp_path / "sample.env").write_text("A=b\n")
    (tmp_path / "sample.env.example").write_text("A=b\n")
    assert cli(["check", str(tmp_path / "sample.env")]) == 0


def test_check_infers_env_example_from_dotenv_name(tmp_path):
    (tmp_path / ".env").write_text("A=b\n")
    (tmp_path / ".env.example").write_text("A=b\n")
    assert cli(["check", str(tmp_path)]) == 0