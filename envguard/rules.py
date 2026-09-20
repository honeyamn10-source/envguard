"""Builtin secret detector ruleset."""
from __future__ import annotations

import re
from dataclasses import dataclass
from re import Pattern
from typing import Callable

from envguard.entropy import is_high_entropy

SEVERITIES = ("critical", "high", "medium", "low")
SEVERITY_ORDER = {name: index for index, name in enumerate(SEVERITIES)}

_CREDENTIAL_KEY_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?key|auth[_-]?token|client[_-]?secret|"
    r"credential|passwd|password|pwd|secret|token)",
    re.IGNORECASE,
)
_HEX_TOKEN_RE = re.compile(r"(^|[^0-9a-fA-F])([0-9a-fA-F]{32,})(?![0-9a-fA-F])")
_BASE64_TOKEN_RE = re.compile(r"(^|[^A-Za-z0-9+/])([A-Za-z0-9+/]{32,}={0,2})(?![A-Za-z0-9+/=])")

_PLACEHOLDER_WORD = r"(?:api|key|token|secret|password|passwd|pwd|value|user|username)"
_SEP = r"[-_ ]*"
_PLACEHOLDER_PHRASES = [
    r"<[^>]{0,40}>",
    r"\.\.\.",
    r"x{3,}",
    r"\*{4,}",
    r"changeme\d*",
    r"replaceme",
    r"placeholder",
    r"dummy",
    r"foobar",
    r"todo",
    r"(?:enter|insert|put|set|replace)" + _SEP + r"(?:your|my|the|a|an|default)?" + _SEP + _PLACEHOLDER_WORD + _SEP + r"(?:here|value)?",
    r"(?:your|my|our|default|the)" + _SEP + r"(?:api" + _SEP + r")?" + _SEP + _PLACEHOLDER_WORD + _SEP + r"(?:here|value)?",
    _PLACEHOLDER_WORD + _SEP + r"here",
    r"(?:test|example|sample|demo)" + _SEP + _PLACEHOLDER_WORD,
    r"(?:example|sample|demo|test)" + _SEP + r"\d*",
]
_PLACEHOLDER_RE = re.compile(
    r"^(?:[^A-Za-z0-9]*)(?:" + "|".join(_PLACEHOLDER_PHRASES) + r")(?:[^A-Za-z0-9]*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RawMatch:
    """A raw regex match used by the scanner.

    Attributes:
        start: Absolute start offset within the scanned text.
        end: Absolute end offset within the scanned text.
        value: The secret-ish value to mask and validate.
        line: Pre-computed 1-based line number when available.
    """

    start: int
    end: int
    value: str
    line: int | None = None


@dataclass(frozen=True)
class Rule:
    """A builtin detector.

    Attributes:
        name: Unique detector name.
        severity: One of ``critical``, ``high``, ``medium``, ``low``.
        description: Human-readable description used in findings.
        pattern: Raw regular expression the detector is based on.
        matcher: Function that returns every match of the detector in a text.
        validator: Optional predicate on the matched value.
    """

    name: str
    severity: str
    description: str
    pattern: str
    matcher: Callable[[str], list[RawMatch]]
    validator: Callable[[str], bool] | None = None

    def __post_init__(self) -> None:
        """Validate the rule at construction time."""
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity!r} for rule {self.name!r}")


def regex_matcher(pattern: str, flags: int = 0, capture_group: int | None = None) -> Callable[[str], list[RawMatch]]:
    """Build a matcher that runs a compiled regex over the whole text.

    Args:
        pattern: Regular expression source.
        flags: Regex flags used when compiling.
        capture_group: Optional group number whose value is the secret.

    Returns:
        A matcher callable used by the scanning engine.
    """
    compiled: Pattern = re.compile(pattern, flags)

    def matcher(text: str) -> list[RawMatch]:
        results: list[RawMatch] = []
        for match in compiled.finditer(text):
            value = match.group(capture_group) if capture_group is not None else match.group(0)
            results.append(
                RawMatch(
                    start=match.start(),
                    end=match.end(),
                    value=value,
                )
            )
        return results

    return matcher


def entropy_matcher(kind: str) -> Callable[[str], list[RawMatch]]:
    """Build a matcher for one of the high-entropy detectors.

    Tokens are only reported when a credential-like key name appears on the
    same line and the token passes the entropy heuristics. Base64 tokens that
    overlap a stronger detector (AWS secrets, GitHub PATs, JWTs, Stripe or
    OpenAI keys) are suppressed to avoid duplicate findings.

    Args:
        kind: Either ``"hex"`` or ``"base64"``.

    Returns:
        A matcher callable used by the scanning engine.
    """

    def matcher(text: str) -> list[RawMatch]:
        results: list[RawMatch] = []
        strong_spans: list[tuple[int, int]] = []
        if kind == "base64":
            for token_start, token_end in _STRONG_GUARD_PAIRS:
                if _STRONG_GUARD_RE[token_start].search(text) is not None:
                    for match in _STRONG_GUARD_RE[token_start].finditer(text):
                        _mark_span(strong_spans, (match.start(), match.end()))
        offset = 0
        for line in text.splitlines(keepends=True):
            if _CREDENTIAL_KEY_RE.search(line) is None:
                offset += len(line)
                continue
            token_re = _HEX_TOKEN_RE if kind == "hex" else _BASE64_TOKEN_RE
            for match in token_re.finditer(line):
                token_group = 2
                token = match.group(token_group)
                span_start = offset + match.start(token_group)
                span_end = offset + match.end(token_group)
                if kind == "base64" and _overlaps(strong_spans, span_start, span_end):
                    continue
                if not _passes_entropy(kind, token):
                    continue
                results.append(RawMatch(start=span_start, end=span_end, value=token))
            offset += len(line)
        return results

    return matcher


def _mark_span(spans: list[tuple[int, int]], span: tuple[int, int]) -> None:
    """Append a span, merging with the previous span when overlapping.

    Args:
        spans: Accumulated span list.
        span: New span to add.
    """
    if spans and span[0] <= spans[-1][1]:
        previous = spans.pop()
        spans.append((min(previous[0], span[0]), max(previous[1], span[1])))
    else:
        spans.append(span)


def _overlaps(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    """Check whether an interval overlaps any span.

    Args:
        spans: Sorted, non-overlapping spans.
        start: Interval start.
        end: Interval end.

    Returns:
        ``True`` when any span overlaps the interval.
    """
    for span in spans:
        if span[0] <= start < span[1]:
            return True
        if start <= span[0] < end:
            return True
    return False


def _passes_entropy(kind: str, token: str) -> bool:
    """Gate a token through the entropy heuristics for its kind.

    Args:
        kind: Either ``"hex"`` or ``"base64"``.
        token: The candidate token.

    Returns:
        ``True`` when the token passes the heuristic gates.
    """
    candidate = token.rstrip("=")
    if len(candidate) < 32:
        return False
    if kind == "hex":
        if not _is_pure_hex(candidate):
            return False
        return is_high_entropy(candidate, "hex")
    if _is_pure_hex(candidate):
        return False
    return is_high_entropy(candidate, "base64")


def _is_pure_hex(token: str) -> bool:
    """Check whether a token only contains hexadecimal characters.

    Args:
        token: The token to inspect.

    Returns:
        ``True`` when the token is made of hex characters only.
    """
    return re.fullmatch(r"[0-9a-fA-F]+", token) is not None


_STRONG_GUARD_PATTERNS = {
    "aws-secret-access-key": r"aws[^\r\n]{0,20}?[:=][\s\"']*[A-Za-z0-9/+=]{40}",
    "github-pat": r"gh[pousr]_[A-Za-z0-9]{35,}|github_pat_[A-Za-z0-9_]{22,}",
    "jwt": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "stripe-key": r"sk_live_[0-9A-Za-z]{20,}",
    "openai-api-key": r"sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}",
}


def _compile_guard_pair(name: str, source: str) -> tuple[str, Pattern]:
    """Compile a guard regex keyed by detector name.

    Args:
        name: Detector name.
        source: Regex source.

    Returns:
        A ``(name, compiled)`` tuple.
    """
    return (name, re.compile(source, re.IGNORECASE))


_STRONG_GUARD_PAIRS: list[tuple[str, Pattern]] = [
    _compile_guard_pair(name, source) for name, source in _STRONG_GUARD_PATTERNS.items()
]
_STRONG_GUARD_RE: dict = {name: compiled for name, compiled in _STRONG_GUARD_PAIRS}


def extract_strong_spans(text: str, ordered_names: list[str]) -> list[tuple[int, int]]:
    """Return the spans of strong detectors present in a text.

    Args:
        text: Text to scan.
        ordered_names: Detector names whose spans are wanted.

    Returns:
        Merged, sorted non-overlapping spans.
    """
    spans: list[tuple[int, int]] = []
    for name in ordered_names:
        compiled = _STRONG_GUARD_RE.get(name)
        if compiled is None:
            continue
        for match in compiled.finditer(text):
            _mark_span(spans, (match.start(), match.end()))
    return spans


AWS_ACCESS_KEY_ID_RULE = Rule(
    name="aws-access-key-id",
    severity="critical",
    description="AWS Access Key ID",
    pattern=r"AKIA[0-9A-Z]{16}",
    matcher=regex_matcher(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
)

AWS_SECRET_ACCESS_KEY_RULE = Rule(
    name="aws-secret-access-key",
    severity="critical",
    description="AWS Secret Access Key",
    pattern=r"aws[^\r\n]{0,20}?[:=][\s\"']*[A-Za-z0-9/+=]{40}",
    matcher=regex_matcher(r"aws[^\r\n]{0,20}?[:=][\s\"']*([A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])", re.IGNORECASE, capture_group=1),
)

GITHUB_PAT_RULE = Rule(
    name="github-pat",
    severity="high",
    description="GitHub Personal Access Token",
    pattern=r"gh[pousr]_[A-Za-z0-9]{35,}|github_pat_[A-Za-z0-9_]{22,}",
    matcher=regex_matcher(r"gh[pousr]_[A-Za-z0-9]{35,}|github_pat_[A-Za-z0-9_]{22,}"),
)

SLACK_TOKEN_RULE = Rule(
    name="slack-token",
    severity="high",
    description="Slack API token",
    pattern=r"xox[baprs]-[0-9a-zA-Z-]{10,48}",
    matcher=regex_matcher(r"xox[baprs]-[0-9a-zA-Z-]{10,48}"),
)

STRIPE_KEY_RULE = Rule(
    name="stripe-key",
    severity="critical",
    description="Stripe secret API key",
    pattern=r"sk_live_[0-9A-Za-z]{20,}",
    matcher=regex_matcher(r"sk_live_[0-9A-Za-z]{20,}"),
)

OPENAI_API_KEY_RULE = Rule(
    name="openai-api-key",
    severity="high",
    description="OpenAI API key",
    pattern=r"sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}",
    matcher=regex_matcher(r"sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,}"),
)

PRIVATE_KEY_RULE = Rule(
    name="private-key",
    severity="critical",
    description="Private key material",
    pattern=r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |)PRIVATE KEY-----",
    matcher=regex_matcher(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |)PRIVATE KEY-----"),
)

POSTGRESQL_URL_RULE = Rule(
    name="postgresql-url",
    severity="high",
    description="PostgreSQL connection string with embedded credentials",
    pattern=r"(?:postgres|postgresql)://[^:\s]+:[^@\s]+@",
    matcher=regex_matcher(r"(?:postgres|postgresql)://[^:\s]+:[^@\s]+@", re.IGNORECASE),
)

REDIS_URL_RULE = Rule(
    name="redis-url",
    severity="high",
    description="Redis connection string with embedded password",
    pattern=r"rediss?://[^:\s]+:[^@\s]+@",
    matcher=regex_matcher(r"rediss?://[^:\s]+:[^@\s]+@", re.IGNORECASE),
)

MYSQL_URL_RULE = Rule(
    name="mysql-url",
    severity="high",
    description="MySQL connection string with embedded credentials",
    pattern=r"mysql://[^:\s]+:[^@\s]+@",
    matcher=regex_matcher(r"mysql://[^:\s]+:[^@\s]+@", re.IGNORECASE),
)

MONGODB_URL_RULE = Rule(
    name="mongodb-url",
    severity="high",
    description="MongoDB connection string with embedded credentials",
    pattern=r"mongodb(?:\+srv)?://[^:\s]+:[^@\s]+@",
    matcher=regex_matcher(r"mongodb(?:\+srv)?://[^:\s]+:[^@\s]+@", re.IGNORECASE),
)

JWT_RULE = Rule(
    name="jwt",
    severity="high",
    description="JSON Web Token (JWT)",
    pattern=r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    matcher=regex_matcher(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
)

HIGH_ENTROPY_HEX_RULE = Rule(
    name="high-entropy-hex",
    severity="medium",
    description="High-entropy hexadecimal token next to a credential name",
    pattern=r"(?:^|[^0-9a-fA-F])([0-9a-fA-F]{32,})(?![0-9a-fA-F])",
    matcher=entropy_matcher("hex"),
)

HIGH_ENTROPY_BASE64_RULE = Rule(
    name="high-entropy-base64",
    severity="medium",
    description="High-entropy base64 token next to a credential name",
    pattern=r"(?:^|[^A-Za-z0-9+/=])([A-Za-z0-9+/]{32,}={0,2})(?![A-Za-z0-9+/=])",
    matcher=entropy_matcher("base64"),
)

BUILTIN_RULES: list[Rule] = [
    AWS_ACCESS_KEY_ID_RULE,
    AWS_SECRET_ACCESS_KEY_RULE,
    GITHUB_PAT_RULE,
    SLACK_TOKEN_RULE,
    STRIPE_KEY_RULE,
    OPENAI_API_KEY_RULE,
    PRIVATE_KEY_RULE,
    POSTGRESQL_URL_RULE,
    REDIS_URL_RULE,
    MYSQL_URL_RULE,
    MONGODB_URL_RULE,
    JWT_RULE,
    HIGH_ENTROPY_HEX_RULE,
    HIGH_ENTROPY_BASE64_RULE,
]

_RULES_BY_NAME: dict = {rule.name: rule for rule in BUILTIN_RULES}


def get_rule(name: str) -> Rule:
    """Look up a rule by detector name.

    Args:
        name: Detector name.

    Returns:
        The matching rule.

    Raises:
        KeyError: When no rule has that name.
    """
    return _RULES_BY_NAME[name]


def looks_like_placeholder(value: str) -> bool:
    """Detect example/placeholder values that should never be reported.

    Recognises ``<...>`` markers, ellipses, runs of ``x`` or ``*`` and common
    English placeholder words such as ``changeme``, ``YOUR_KEY_HERE`` or
    ``example``.

    Args:
        value: The matched secret candidate.

    Returns:
        ``True`` when the value is a placeholder.
    """
    if not value:
        return True
    return _PLACEHOLDER_RE.search(value) is not None


def mask_secret(value: str) -> str:
    """Mask a secret for safe display, keeping a short preview.

    Args:
        value: The secret value.

    Returns:
        A masked preview like ``AKIA****ABCD``.
    """
    cleaned = re.sub(r"\s+", "", value)
    if len(cleaned) <= 8:
        return "*" * 4
    return cleaned[:4] + "*" * 4 + cleaned[-4:]


def validate_severity(csv_value: str | None) -> set[str] | None:
    """Parse a ``--severity`` value into a set of allowed severities.

    Args:
        csv_value: Comma-separated severity names, or ``None``.

    Returns:
        A set of severity names, or ``None`` when no filter was given.

    Raises:
        ValueError: When a severity name is unknown.
    """
    if csv_value is None:
        return None
    names = set()
    for raw in csv_value.split(","):
        name = raw.strip().lower()
        if name not in SEVERITIES:
            raise ValueError(f"unknown severity {name!r}; expected one of {', '.join(SEVERITIES)}")
        names.add(name)
    return names


def severity_pass(severity: str, allowed: set[str] | None) -> bool:
    """Check whether a finding's severity passes a filter.

    Args:
        severity: The finding's severity.
        allowed: Allowed severities, or ``None`` for no filtering.

    Returns:
        ``True`` when the finding should be reported.
    """
    if allowed is None:
        return True
    return severity in allowed