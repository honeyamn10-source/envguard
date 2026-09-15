"""Command-line entry point for envguard."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from envguard import __version__
from envguard.check import CheckOptions, format_result, lint, to_json
from envguard.output import format_scan_result, scan_to_json
from envguard.rules import validate_severity
from envguard.scan import ScanError, scan_path

_DESCRIPTION = (
    "Audit your .env files and scan your codebase for leaked secrets "
    "before it's too late."
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        A configured ``ArgumentParser`` with the check and scan subcommands.
    """
    parser = argparse.ArgumentParser(
        prog="envguard",
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"envguard {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    check_parser = subparsers.add_parser(
        "check",
        help="Lint a .env file against a .env.example file",
        description="Lint a .env file against .env.example: missing keys, extra keys, "
        "duplicates, quoting pitfalls, empty required values and malformed lines.",
    )
    check_parser.add_argument("path", nargs="?", default=".", help="directory or .env file (default: current directory)")
    check_parser.add_argument("--example", metavar="PATH", help="path to the .env.example file to compare against")
    check_parser.add_argument("--allow", action="append", default=[], metavar="KEY", help="allow an extra key (repeatable)")
    check_parser.add_argument("--require", action="append", default=[], metavar="KEY", help="require a key to be non-empty (repeatable)")
    check_parser.add_argument("--strict", action="store_true", help="report warnings as errors")
    check_parser.add_argument("--json", action="store_true", help="print machine-readable JSON output")

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a codebase for leaked secrets",
        description="Scan a codebase for likely secrets. Climb the tree, respect "
        ".gitignore and .envguard-ignore files, and report findings per line.",
    )
    scan_parser.add_argument("path", nargs="?", default=".", help="file or directory to scan (default: current directory)")
    scan_parser.add_argument("--format", choices=("human", "json"), default="human", help="output format (default: human)")
    scan_parser.add_argument("--severity", metavar="LEVELS", help="comma-separated severity filter, e.g. critical,high")
    scan_parser.add_argument("--max-findings", type=int, metavar="N", help="stop scanning after N findings")

    return parser


def _resolve_check_paths(path: Path, example: Optional[Path]):
    """Resolve the env file and example file to compare.

    Args:
        path: Directory or explicit ``.env`` file.
        example: Explicit example path, or ``None``.

    Returns:
        A ``(env_path, example_path)`` tuple.

    Raises:
        ValueError: When either file is missing.
    """
    if not path.exists():
        raise ValueError(f"path does not exist: {path}")
    if path.is_file():
        env_path = path
        if example is not None:
            example_path = example
        elif path.name == ".env":
            example_path = path.parent / ".env.example"
        else:
            example_path = path.with_name(path.stem + ".env.example")
    else:
        env_path = path / ".env"
        example_path = example if example is not None else path / ".env.example"
    if not env_path.is_file():
        raise ValueError(f"no .env file found in {path}")
    if not example_path.is_file():
        raise ValueError(f"no .env.example file found in {example_path.parent}")
    return env_path, example_path


def run_check(args: argparse.Namespace) -> int:
    """Execute the check subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code: 0 when the file passes, 1 when issues exist, 2 on errors.
    """
    options = CheckOptions(allow=args.allow, require=args.require, strict=args.strict)
    try:
        env_path, example_path = _resolve_check_paths(Path(args.path), Path(args.example) if args.example else None)
    except ValueError as error:
        print(f"envguard: error: {error}", file=sys.stderr)
        return 2
    try:
        result = lint(env_path, example_path, options)
    except (OSError, UnicodeError) as error:
        print(f"envguard: error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(to_json(result), indent=2))
    else:
        print(format_result(result))
    return 0 if result.ok else 1


def run_scan(args: argparse.Namespace) -> int:
    """Execute the scan subcommand.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code: 0 when no findings exist, 1 when findings exist, 2 on errors.
    """
    try:
        allowed = validate_severity(args.severity)
    except ValueError as error:
        print(f"envguard: error: {error}", file=sys.stderr)
        return 2
    if args.max_findings is not None and args.max_findings < 1:
        print(f"envguard: error: --max-findings must be >= 1, got {args.max_findings}", file=sys.stderr)
        return 2
    try:
        result = scan_path(Path(args.path), severity=allowed, max_findings=args.max_findings)
    except (ScanError, OSError) as error:
        print(f"envguard: error: {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(scan_to_json(result), indent=2))
    else:
        print(format_scan_result(result))
    return 0 if result.ok else 1


def cli(argv: Optional[List[str]] = None) -> int:
    """Run the CLI and return its exit code.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        Exit code per the documented contract: 0 pass/help, 1 findings, 2 errors.
    """
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "check":
        return run_check(args)
    return run_scan(args)


def main() -> int:
    """Console script entry point.

    Returns:
        The process exit code.
    """
    return cli(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())