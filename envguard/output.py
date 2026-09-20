"""Human and JSON formatters for scan results."""


from envguard.rules import SEVERITY_ORDER
from envguard.scan import ScanResult


def format_finding(finding) -> str:
    """Render one finding in the standard ``path:line:severity:detector:description`` form.

    Args:
        finding: The finding to render.

    Returns:
        A single colon-separated line.
    """
    return f"{finding.path}:{finding.line}:{finding.severity}:{finding.detector}:{finding.description}"


def _format_table(rows: list[str], title: str) -> str:
    """Render a simple aligned two-column table.

    Args:
        rows: ``detector  count`` style rows.
        title: Table heading.

    Returns:
        A monospace table block.
    """
    if not rows:
        return f"{title}\n  (none)"
    width = max(len(row.split("  ")[0]) for row in rows)
    header = f"{title:<{width}}  {'count':<5}"
    separator = "-" * (width + 8)
    body = [f"{row.split('  ')[0]:<{width}}  {row.split('  ')[1]:>5}" for row in rows]
    return "\n".join([header, separator] + body)


def format_scan_result(result: ScanResult) -> str:
    """Render a ``ScanResult`` for human consumption.

    Args:
        result: The scan result.

    Returns:
        Multi-line human-readable output with findings and a summary table.
    """
    parts = [f"scanning {result.root}"]
    parts.extend(format_finding(finding) for finding in result.findings)
    parts.append("")
    parts.append(f"Summary: {len(result.findings)} finding(s) across {result.files_scanned} file(s)")

    severity_counts = result.counts_by_severity()
    ordered = [
        f"{name}  {severity_counts.get(name, 0)}"
        for name in sorted(severity_counts, key=lambda name: SEVERITY_ORDER.get(name, 99))
    ]
    if ordered:
        parts.append(_format_table(ordered, "severity"))

    detector_rows = [f"{name}  {count}" for name, count in sorted(result.counts_by_detector().items())]
    if detector_rows:
        parts.append(_format_table(detector_rows, "detector"))

    if result.truncated:
        parts.append("")
        parts.append(f"truncated: stopped after {len(result.findings)} finding(s)")
    return "\n".join(parts)


def scan_to_json(result: ScanResult) -> dict:
    """Serialise a ``ScanResult`` into a JSON-safe mapping.

    Args:
        result: The scan result.

    Returns:
        Machine-readable representation.
    """
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    severity_counts.update(result.counts_by_severity())
    findings = [
        {
            "path": finding.path,
            "line": finding.line,
            "severity": finding.severity,
            "detector": finding.detector,
            "description": finding.description,
            "secret": finding.secret,
        }
        for finding in result.findings
    ]
    return {
        "command": "scan",
        "root": result.root,
        "files_scanned": result.files_scanned,
        "files_skipped": result.files_skipped,
        "truncated": result.truncated,
        "findings": findings,
        "summary": {
            "by_severity": severity_counts,
            "by_detector": result.counts_by_detector(),
        },
    }


def error_json(message: str, command: str) -> str:
    """Render an error payload as JSON.

    Args:
        message: Human-readable error message.
        command: The command that failed, e.g. ``"scan"``.

    Returns:
        A single JSON object.
    """
    import json

    payload = {"command": command, "error": message}
    return json.dumps(payload, indent=2)