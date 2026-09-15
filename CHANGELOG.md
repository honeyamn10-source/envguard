# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-15

### Added

- `envguard check`: lint a `.env` file against a `.env.example`.
  - Detects missing, extra and duplicate keys.
  - Detects unquoted values containing `#` or spaces.
  - Detects empty values for required keys.
  - Detects malformed lines and commented-out keys.
  - `--allow`, `--require`, `--strict`, `--json` flags.
- `envguard scan`: codebase secret scanner.
  - 14 builtin detectors (AWS, GitHub, Slack, Stripe, OpenAI, private keys,
    connection strings, JWTs, high-entropy hex/base64).
  - Weighted Shannon entropy gating with placeholder suppression.
  - gitignore-aware traversal (root, nested, `.git/info/exclude`, builtin list).
  - `.envguard-ignore` file with `file:detector` scoping.
  - Text/binary and 1MB size filtering, `--severity` filter, `--max-findings`,
    human and JSON output.
- Exit-code contract: `0` pass, `1` findings, `2` usage/runtime error.
- Pre-commit hook definitions (`envguard-check`, `envguard-scan`).
- Packaging (pyproject.toml), LICENSE, docs and community files.
- Test-suite with 143 tests covering the linting engine, every detector,
  ignore semantics, entropy heuristics and CLI wiring.

[0.1.0]: https://github.com/honeyamn10-source/envguard/releases/tag/v0.1.0