"""The ``.env`` linting engine."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.@-]*$")
_QUOTED_VALUE_RE = re.compile(r"^([\"'])(.*)\1\s*(?:#.*)?$", re.DOTALL)
_EXPORT_PREFIX = "export "
_COMMENTED_KEY_RE = re.compile(r"^#\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_.@-]*\s*=")


@dataclass(frozen=True)
class EnvEntry:
    """A parsed key/value entry from a dotenv file.

    Attributes:
        key: The variable name.
        value: The parsed value (quotes stripped).
        quoted: Whether the value was written with surrounding quotes.
        line: 1-based line number.
    """

    key: str
    value: str
    quoted: bool
    line: int


@dataclass(frozen=True)
class CheckIssue:
    """A single lint finding for a ``.env`` file.

    Attributes:
        code: Stable machine-readable code.
        line: 1-based line number, or ``None`` for file-level findings.
        severity: Either ``"warning"`` or ``"error"``.
        message: Human-readable description.
    """

    code: str
    line: int | None
    severity: str
    message: str


@dataclass
class CheckOptions:
    """Options controlling how the linter behaves.

    Attributes:
        allow: Keys allowed to exist in the ``.env`` but not the example.
        require: Keys that must have a non-empty value regardless of the example.
        strict: Upgrade every warning to an error in the result.
    """

    allow: list[str] = field(default_factory=list)
    require: list[str] = field(default_factory=list)
    strict: bool = False


@dataclass
class CheckResult:
    """The outcome of linting one ``.env`` against its example.

    Attributes:
        env_path: Path of the linted ``.env`` file.
        example_path: Path of the example file used as the source of truth.
        issues: Every finding, ordered by line then code.
        keys: Parsed keys of the ``.env`` file in declaration order.
    """

    env_path: str
    example_path: str
    issues: list[CheckIssue] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether the file passed without any issues."""
        return not self.issues

    @property
    def warnings(self) -> int:
        """Number of warning-severity issues."""
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def errors(self) -> int:
        """Number of error-severity issues."""
        return sum(1 for issue in self.issues if issue.severity == "error")


def _split_lines(text: str) -> list[str]:
    """Split text into lines preserving them for parsing.

    Args:
        text: Raw file content.

    Returns:
        The list of lines.
    """
    text = text.removesuffix("\n")
    return text.split("\n")


def parse_env(text: str) -> dict[str, EnvEntry]:
    """Parse dotenv content into its key/value entries.

    Duplicate keys are resolved last-value-wins. Malformed lines are skipped
    (the linter reports them separately). Comment and blank lines are ignored.

    Args:
        text: Raw ``.env`` or ``.env.example`` content.

    Returns:
        A mapping of key to its winning ``EnvEntry``.
    """
    entries: dict[str, EnvEntry] = {}
    for line_number, raw in enumerate(_split_lines(text), start=1):
        content = raw.strip()
        if not content or content.startswith(("#", ";")):
            continue
        if _COMMENTED_KEY_RE.match(raw):
            continue
        if content.startswith(_EXPORT_PREFIX):
            content = content[len(_EXPORT_PREFIX):].strip()
        if "=" not in content:
            continue
        key_raw, value_raw = content.split("=", 1)
        key = key_raw.strip()
        value, quoted = _parse_value(value_raw)
        if not _KEY_RE.match(key):
            continue
        entries[key] = EnvEntry(key=key, value=value, quoted=quoted, line=line_number)
    return entries


def _parse_value(value_raw: str):
    """Parse a raw value into (value, quoted).

    Args:
        value_raw: The raw string after ``=``.

    Returns:
        A ``(value, quoted)`` tuple.
    """
    stripped = value_raw.strip()
    quoted_match = _QUOTED_VALUE_RE.match(stripped)
    if quoted_match:
        return quoted_match.group(2), True
    return stripped, False


def lint_texts(env_text: str, example_text: str, options: CheckOptions | None = None) -> list[CheckIssue]:
    """Lint env content against example content without touching the filesystem.

    Args:
        env_text: Raw ``.env`` content.
        example_text: Raw ``.env.example`` content.
        options: Optional linter options; defaults to a plain configuration.

    Returns:
        Every issue, ordered by line then code.
    """
    opts = options or CheckOptions()
    env_entries = parse_env(env_text)
    example_entries = parse_env(example_text)
    allow_set = set(opts.allow)
    issues: list[CheckIssue] = []

    counts: dict[str, int] = {}
    lines_per_key: dict[str, list[int]] = {}

    for line_number, raw in enumerate(_split_lines(env_text), start=1):
        content = raw.strip()
        if not content:
            continue
        stripped_raw = raw.lstrip()
        if content.startswith(("#", ";")):
            commented = _COMMENTED_KEY_RE.match(stripped_raw)
            if commented:
                name = commented.group(0).lstrip("#").strip()
                issues.append(
                    CheckIssue(
                        code="commented-key",
                        line=line_number,
                        severity="warning",
                        message=f"key appears commented out in a comment-only line: {name}",
                    )
                )
            continue
        if content.startswith(_EXPORT_PREFIX):
            content = content[len(_EXPORT_PREFIX):].strip()
        if "=" not in content:
            issues.append(
                CheckIssue(
                    code="malformed-line",
                    line=line_number,
                    severity="error",
                    message=f"line contains no '=' separator: {raw.strip()!r}",
                )
            )
            continue
        key_raw, value_raw = content.split("=", 1)
        key = key_raw.strip()
        if not _KEY_RE.match(key):
            issues.append(
                CheckIssue(
                    code="malformed-line",
                    line=line_number,
                    severity="error",
                    message=f"invalid key name {key!r} on this line",
                )
            )
            continue
        counts[key] = counts.get(key, 0) + 1
        lines_per_key.setdefault(key, []).append(line_number)
        stripped_value = value_raw.strip()
        if _QUOTED_VALUE_RE.match(stripped_value):
            continue
        if "#" in stripped_value:
            issues.append(
                CheckIssue(
                    code="unquoted-hash",
                    line=line_number,
                    severity="warning",
                    message=f"unquoted value for {key!r} contains '#' and may be truncated on parsing",
                )
            )
        elif re.search(r"\s", value_raw):
            issues.append(
                CheckIssue(
                    code="unquoted-space",
                    line=line_number,
                    severity="warning",
                    message=f"unquoted value for {key!r} contains spaces and may break dotenv parsing",
                )
            )

    for key, count in counts.items():
        if count > 1:
            issues.append(
                CheckIssue(
                    code="duplicate-key",
                    line=lines_per_key[key][0],
                    severity="warning",
                    message=f"key {key!r} appears {count} times; the last value wins",
                )
            )

    for entry in env_entries.values():
        if entry.key in example_entries or entry.key in allow_set:
            continue
        issues.append(
            CheckIssue(
                code="extra-key",
                line=entry.line,
                severity="warning",
                message=f"key {entry.key!r} is present in the env file but not in the example",
            )
        )

    missing_candidates = list(example_entries.keys())
    missing_candidates.extend(key for key in opts.require if key not in example_entries)
    for key in missing_candidates:
        if key in env_entries:
            continue
        issues.append(
            CheckIssue(
                code="missing-key",
                line=None,
                severity="warning",
                message=f"key {key!r} is present in the example but missing from the env file",
            )
        )

    required = {key for key, entry in example_entries.items() if entry.value != ""}
    required.update(opts.require)
    for key in required:
        entry = env_entries.get(key)
        if entry is not None and entry.value == "":
            issues.append(
                CheckIssue(
                    code="empty-required",
                    line=entry.line,
                    severity="error",
                    message=f"required key {key!r} has an empty value",
                )
            )

    if opts.strict:
        issues = [
            CheckIssue(code=issue.code, line=issue.line, severity="error", message=issue.message)
            if issue.severity == "warning"
            else issue
            for issue in issues
        ]

    return sorted(
        issues,
        key=lambda issue: (issue.line if issue.line is not None else 10 ** 9, issue.code, issue.message),
    )


def lint(env_path: Path, example_path: Path, options: CheckOptions | None = None) -> CheckResult:
    """Lint one ``.env`` file against one example file.

    Args:
        env_path: Path of the file to lint.
        example_path: Path of the example file.
        options: Optional linter options.

    Returns:
        The ``CheckResult`` for the pair of files.
    """
    opts = options or CheckOptions()
    env_text = env_path.read_text(encoding="utf-8-sig")
    example_text = example_path.read_text(encoding="utf-8-sig")
    issues = lint_texts(env_text, example_text, opts)
    keys = list(parse_env(env_text).keys())
    return CheckResult(env_path=str(env_path), example_path=str(example_path), issues=issues, keys=keys)


def _summarize(issues: Sequence[CheckIssue]) -> str:
    """Render the human-readable summary line for issues.

    Args:
        issues: The issues to summarise.

    Returns:
        A summary string such as ``4 issues (3 warnings, 1 error)``.
    """
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    errors = len(issues) - warnings
    return f"{len(issues)} issue(s) ({warnings} warning(s), {errors} error(s))"


def format_result(result: CheckResult) -> str:
    """Render a ``CheckResult`` for human consumption.

    Args:
        result: The lint result.

    Returns:
        Multi-line human-readable output.
    """
    basename = str(Path(result.env_path).name) or result.env_path
    lines = [f"checking {result.env_path} against {result.example_path}"]
    for issue in result.issues:
        line = issue.line if issue.line is not None else 0
        lines.append(f"{basename}:{line}:{issue.severity}:{issue.code}:{issue.message}")
    lines.append("")
    lines.append(f"Summary: {_summarize(result.issues)}")
    return "\n".join(lines)


def to_json(result: CheckResult) -> dict:
    """Serialise a ``CheckResult`` into a JSON-safe mapping.

    Args:
        result: The lint result.

    Returns:
        Machine-readable representation.
    """
    issues = [
        {
            "code": issue.code,
            "line": issue.line,
            "severity": issue.severity,
            "message": issue.message,
        }
        for issue in result.issues
    ]
    return {
        "command": "check",
        "env": result.env_path,
        "example": result.example_path,
        "keys": result.keys,
        "ok": result.ok,
        "issues": issues,
        "counts": {"warning": result.warnings, "error": result.errors},
    }