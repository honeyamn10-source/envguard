# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Advanced, dependency-free website design system with dark/light themes,
  persistent theme toggle, responsive mobile navigation, scroll progress,
  active-section highlighting and reveal-on-scroll states.
- Interactive workflow explorer with keyboard navigation, a tabbed command
  console with copy feedback, a searchable/filterable 14-detector catalog,
  exit-code reference, FAQ accordion and back-to-top control.
- Opt-in website translation trial using a pinned, hash-verified vendored copy
  of translate.js. Only the public guide container `#docs-content` is sent to
  Microsoft Translator; commands, buttons, terminal/scan output, search input
  and identifiers are excluded.
- `docs/TRANSLATION.md` documenting the endpoint, privacy disclosure, SEO
  caveat, failure handling, advanced UI interactions and manual test checklist.
- Static regression checks in `tests/test_website_translation.py` covering the
  hardened translation wiring and the advanced UI contracts.

### Fixed

- Translation scope is re-resolved on every language switch, stale speed-test
  storage cannot re-enable fallback hosts, network failures are detected
  instead of being reported as success, cached translations are handled, the
  failure path restores the original English DOM, and workflow / command-panel
  / detector-filter changes use a clean retranslation pass via a small custom
  event.
- Language controls and the privacy notice are styled for the advanced website
  at desktop, tablet and small-mobile widths.
- Detector severity counts now match `envguard/rules.py` (4 critical, 8 high,
  2 medium), and hidden command/search controls are excluded from translation.

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