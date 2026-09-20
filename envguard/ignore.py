"""Gitignore-style ignore matching and ``.envguard-ignore`` parsing."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass

BUILTIN_IGNORE_PATTERNS = [
    ".git/",
    ".hg/",
    ".svn/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "node_modules/",
    "dist/",
    "build/",
    ".cache/",
    ".tox/",
    ".eggs/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "*.py[cod]",
    "*.egg-info/",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "*.min.js",
    "*.min.css",
    "*.map",
]


@dataclass(frozen=True)
class IgnoreRule:
    """A single normalised gitignore rule.

    Attributes:
        pattern: The glob pattern without leading ``!`` or ``/`` markers.
        negated: ``True`` when the rule re-includes a previously ignored path.
        dir_only: ``True`` when the pattern only applies to directories.
        anchored: ``True`` when the pattern is anchored to its base directory.
        base: Repo-relative directory the pattern was declared in.
    """

    pattern: str
    negated: bool
    dir_only: bool
    anchored: bool
    base: str


class IgnoreMatcher:
    """A small gitignore matcher supporting the common glob forms.

    Supports ``dir/`` directories, ``/root-anchored`` paths, ``*.ext`` globs,
    ``!`` negations and per-directory ``.gitignore`` files. Ordering follows
    git semantics: the last matching rule for a path wins.
    """

    def __init__(self) -> None:
        """Initialise an empty matcher."""
        self._rules: list[IgnoreRule] = []

    def add(self, patterns: list[str], base: str = "") -> None:
        """Add patterns, optionally scoped to a repo-relative base directory.

        Args:
            patterns: Raw lines from a ``.gitignore`` file.
            base: Repo-relative directory the patterns apply to.
        """
        for raw in patterns:
            rule = self._parse(raw, base)
            if rule is not None:
                self._rules.append(rule)

    @staticmethod
    def _parse(raw: str, base: str) -> IgnoreRule | None:
        """Normalise one raw pattern line into an ``IgnoreRule``.

        Args:
            raw: A single line from a gitignore file.
            base: Repo-relative directory the pattern applies to.

        Returns:
            A parsed rule, or ``None`` for blank/comment lines.
        """
        line = raw.strip()
        if not line or line.startswith("#"):
            return None
        negated = False
        if line.startswith("!"):
            negated = True
            line = line[1:].lstrip()
        if not line:
            return None
        dir_only = False
        if line.endswith("/"):
            dir_only = True
            line = line[:-1]
        anchored = False
        if line.startswith("/"):
            anchored = True
            line = line[1:]
        if not line:
            return None
        return IgnoreRule(
            pattern=line,
            negated=negated,
            dir_only=dir_only,
            anchored=anchored,
            base=base.strip("/"),
        )

    @staticmethod
    def _applies(rule: IgnoreRule, relpath: str) -> bool:
        """Check whether a rule is scoped to the given path.

        Args:
            rule: The rule to test.
            relpath: Repo-relative path, e.g. ``src/db.py``.

        Returns:
            ``True`` when the rule can influence the path.
        """
        if not rule.base:
            return True
        return relpath == rule.base or relpath.startswith(rule.base + "/")

    @staticmethod
    def _matches(rule: IgnoreRule, relpath: str, is_dir: bool) -> bool:
        """Evaluate one rule against a path.

        Args:
            rule: The rule to test.
            relpath: Repo-relative path.
            is_dir: Whether the path refers to a directory.

        Returns:
            ``True`` when the glob matches the path.
        """
        parts = relpath.split("/")
        if rule.anchored:
            return fnmatch.fnmatch(relpath, rule.pattern)
        if rule.dir_only:
            depth = len(parts) if is_dir else len(parts) - 1
            for start in range(depth):
                for end in range(start + 1, depth + 1):
                    if fnmatch.fnmatch("/".join(parts[start:end]), rule.pattern):
                        return True
            return False
        if "/" in rule.pattern:
            return fnmatch.fnmatch(relpath, rule.pattern) or any(
                fnmatch.fnmatch(part, rule.pattern) for part in parts
            )
        return any(fnmatch.fnmatch(part, rule.pattern) for part in parts)

    def is_ignored(self, relpath: str, is_dir: bool = False) -> bool:
        """Decide whether a path is ignored.

        Args:
            relpath: Repo-relative path.
            is_dir: Whether the path refers to a directory.

        Returns:
            ``True`` when the last matching rule ignores the path.
        """
        relpath = relpath.strip("/")
        if not relpath:
            return False
        ignored = False
        for rule in self._rules:
            if self._applies(rule, relpath) and self._matches(rule, relpath, is_dir):
                ignored = not rule.negated
        return ignored


@dataclass(frozen=True)
class EnvguardIgnoreRule:
    """A single entry from an ``.envguard-ignore`` file.

    Attributes:
        glob: Glob matched against the repo-relative file path.
        detector: Optional detector name the glob applies to.
    """

    glob: str
    detector: str | None = None


def parse_envguard_ignore(text: str) -> list[EnvguardIgnoreRule]:
    """Parse ``.envguard-ignore`` content.

    Lines are one glob per line; ``file:detector`` ignores a specific
    detector in matching files. Blank lines and ``#`` comments are skipped.

    Args:
        text: Raw content of the ignore file.

    Returns:
        The parsed rules in declaration order.
    """
    rules: list[EnvguardIgnoreRule] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            glob_part, detector_part = line.rsplit(":", 1)
            glob_part = glob_part.strip()
            detector_part = detector_part.strip()
            if glob_part:
                rules.append(EnvguardIgnoreRule(glob=glob_part, detector=detector_part))
        else:
            rules.append(EnvguardIgnoreRule(glob=line))
    return rules


def is_suppressed(relpath: str, detector: str, rules: list[EnvguardIgnoreRule]) -> bool:
    """Check whether a finding should be suppressed by ignore rules.

    Args:
        relpath: Repo-relative file path.
        detector: Detector name of the finding.
        rules: Parsed ``.envguard-ignore`` rules.

    Returns:
        ``True`` when any rule suppresses the finding.
    """
    base = relpath.rsplit("/", 1)[-1] if "/" in relpath else relpath
    for rule in rules:
        matched = fnmatch.fnmatch(relpath, rule.glob)
        if "/" not in rule.glob:
            matched = matched or fnmatch.fnmatch(base, rule.glob)
        if not matched:
            continue
        if rule.detector is None or rule.detector == "*":
            return True
        if rule.detector == detector:
            return True
    return False