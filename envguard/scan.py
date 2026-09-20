"""The codebase secret scanning engine."""
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from envguard.ignore import (
    BUILTIN_IGNORE_PATTERNS,
    EnvguardIgnoreRule,
    IgnoreMatcher,
    is_suppressed,
    parse_envguard_ignore,
)
from envguard.rules import (
    BUILTIN_RULES,
    Rule,
    looks_like_placeholder,
    mask_secret,
    severity_pass,
)

MAX_FILE_BYTES = 1_000_000
_BINARY_PROBE_BYTES = 8192
_ENVGUARD_IGNORE_NAME = ".envguard-ignore"


class ScanError(Exception):
    """Raised when a scan cannot be performed."""


@dataclass(frozen=True)
class Finding:
    """A single secret finding.

    Attributes:
        path: Repo-relative path of the file that contains the secret.
        line: 1-based line number.
        severity: One of ``critical``, ``high``, ``medium``, ``low``.
        detector: Name of the detector that matched.
        description: Human-readable detector description.
        secret: Masked preview of the matched value.
    """

    path: str
    line: int
    severity: str
    detector: str
    description: str
    secret: str


@dataclass
class ScanResult:
    """The outcome of a codebase scan.

    Attributes:
        root: The scanned root path.
        findings: All findings sorted by path then line.
        files_scanned: Number of text files scanned.
        files_skipped: Number of files skipped (binary, too large, ignored).
        truncated: Whether scanning stopped early due to ``--max-findings``.
    """

    root: str
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0
    truncated: bool = False

    @property
    def ok(self) -> bool:
        """Whether the scan produced no findings."""
        return not self.findings

    def counts_by_severity(self) -> dict[str, int]:
        """Return finding counts grouped by severity.

        Returns:
            Mapping of severity name to finding count.
        """
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def counts_by_detector(self) -> dict[str, int]:
        """Return finding counts grouped by detector.

        Returns:
            Mapping of detector name to finding count.
        """
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.detector] = counts.get(finding.detector, 0) + 1
        return counts


def _is_binary(data: bytes) -> bool:
    """Detect binary content via NUL bytes in the first chunk.

    Args:
        data: Raw file bytes.

    Returns:
        ``True`` when the content looks binary.
    """
    return b"\x00" in data[:_BINARY_PROBE_BYTES]


def scan_text(text: str, relpath: str, rules: Sequence[Rule] = BUILTIN_RULES) -> list[Finding]:
    """Scan one text buffer with the given rules.

    Args:
        text: Decoded file content.
        relpath: Repo-relative path used in findings.
        rules: Detector rules to apply.

    Returns:
        Findings sorted by line number.
    """
    findings: list[Finding] = []
    for rule in rules:
        for raw_match in rule.matcher(text):
            if looks_like_placeholder(raw_match.value):
                continue
            if rule.validator is not None and not rule.validator(raw_match.value):
                continue
            line = raw_match.line
            if line is None:
                line = text.count("\n", 0, raw_match.start) + 1
            findings.append(
                Finding(
                    path=relpath,
                    line=line,
                    severity=rule.severity,
                    detector=rule.name,
                    description=rule.description,
                    secret=mask_secret(raw_match.value),
                )
            )
    findings.sort(key=lambda finding: finding.line)
    return findings


def _read_envguard_ignore(root: Path) -> list[EnvguardIgnoreRule]:
    """Parse a root-level ``.envguard-ignore`` file when present.

    Args:
        root: Repository root.

    Returns:
        The parsed rules, or an empty list.
    """
    ignore_file = root / _ENVGUARD_IGNORE_NAME
    if not ignore_file.is_file():
        return []
    return parse_envguard_ignore(ignore_file.read_text(encoding="utf-8-sig"))


def _build_matcher(root: Path) -> IgnoreMatcher:
    """Build the ignore matcher from builtin rules and gitignore files.

    Args:
        root: Repository root.

    Returns:
        A configured matcher.
    """
    matcher = IgnoreMatcher()
    matcher.add(BUILTIN_IGNORE_PATTERNS)
    root_gitignore = root / ".gitignore"
    if root_gitignore.is_file():
        matcher.add(root_gitignore.read_text(encoding="utf-8-sig").splitlines())
    info_exclude = root / ".git" / "info" / "exclude"
    if info_exclude.is_file():
        with open(info_exclude, encoding="utf-8-sig") as handle:
            matcher.add(handle.read().splitlines())
    return matcher


def _load_file(full_path: Path, relpath: str, ignored: list[EnvguardIgnoreRule]):
    """Load a file or explain why it must be skipped.

    Args:
        full_path: Absolute path of the file.
        relpath: Repo-relative path.
        ignored: Parsed ``.envguard-ignore`` rules.

    Returns:
        A ``(text, None)`` tuple when the file can be scanned, or
        ``(None, reason)`` when it must be skipped.
    """
    stats = full_path.stat()
    if stats.st_size > MAX_FILE_BYTES:
        return None, f"larger than {MAX_FILE_BYTES} bytes"
    with open(full_path, "rb") as handle:
        data = handle.read()
    if _is_binary(data):
        return None, "binary content"
    if is_suppressed(relpath, "*", ignored):
        return None, "ignored by .envguard-ignore"
    return data.decode("utf-8", errors="replace"), None


def scan_path(
    target: Path,
    severity: set[str] | None = None,
    max_findings: int | None = None,
) -> ScanResult:
    """Scan a file or a whole tree for leaked secrets.

    Args:
        target: File or directory to scan.
        severity: Optional severity filter set, e.g. ``{"critical", "high"}``.
        max_findings: Stop scanning after this many findings.

    Returns:
        The complete ``ScanResult``.

    Raises:
        ScanError: When the target does not exist or is unreadable.
    """
    if not target.exists():
        raise ScanError(f"path does not exist: {target}")
    if target.is_file():
        return _scan_single_file(target, severity, max_findings)

    root = target.resolve()
    matcher = _build_matcher(root)
    ignore_rules = _read_envguard_ignore(root)
    result = ScanResult(root=str(root))

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        dir_rel = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")

        if dir_rel:
            nested_gitignore = os.path.join(dirpath, ".gitignore")
            if os.path.isfile(nested_gitignore):
                with open(nested_gitignore, encoding="utf-8-sig") as handle:
                    matcher.add(handle.read().splitlines(), base=dir_rel)

        for directory in list(dirnames):
            directory_rel = f"{dir_rel}/{directory}" if dir_rel else directory
            if matcher.is_ignored(directory_rel, is_dir=True):
                dirnames.remove(directory)

        for filename in sorted(filenames):
            file_rel = f"{dir_rel}/{filename}" if dir_rel else filename
            if matcher.is_ignored(file_rel, is_dir=False):
                result.files_skipped += 1
                continue
            full_path = Path(dirpath) / filename
            try:
                text, _skip_reason = _load_file(full_path, file_rel, ignore_rules)
            except (OSError, TypeError) as error:
                raise ScanError(f"could not read {file_rel}: {error}") from error
            if text is None:
                result.files_skipped += 1
                continue
            result.files_scanned += 1
            findings = scan_text(text, file_rel, BUILTIN_RULES)
            if severity is not None:
                findings = [finding for finding in findings if severity_pass(finding.severity, severity)]
            findings = [
                finding
                for finding in findings
                if not is_suppressed(file_rel, finding.detector, ignore_rules)
            ]
            result.findings.extend(findings)
            if max_findings is not None and len(result.findings) >= max_findings:
                result.findings = result.findings[:max_findings]
                result.truncated = True
                return result

    result.findings.sort(key=lambda finding: (finding.path, finding.line))
    return result


def _scan_single_file(
    target: Path,
    severity: set[str] | None = None,
    max_findings: int | None = None,
) -> ScanResult:
    """Scan one explicit file path.

    Args:
        target: The file to scan.
        severity: Optional severity filter set.
        max_findings: Stop after this many findings.

    Returns:
        The complete ``ScanResult``.

    Raises:
        ScanError: When the file is too large or binary.
    """
    stats = target.stat()
    if stats.st_size > MAX_FILE_BYTES:
        raise ScanError(f"file is larger than {MAX_FILE_BYTES} bytes: {target}")
    with open(target, "rb") as handle:
        data = handle.read()
    if _is_binary(data):
        raise ScanError(f"file is not a text file: {target}")
    text = data.decode("utf-8", errors="replace")
    findings = scan_text(text, target.name, BUILTIN_RULES)
    if severity is not None:
        findings = [finding for finding in findings if severity_pass(finding.severity, severity)]
    if max_findings is not None and len(findings) > max_findings:
        findings = findings[:max_findings]
    result = ScanResult(root=str(target.parent), findings=findings, files_scanned=1)
    result.truncated = max_findings is not None and len(findings) == max_findings
    return result