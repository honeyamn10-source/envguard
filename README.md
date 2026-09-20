<p align="center">
  <img src="docs/assets/logo.svg" alt="envguard — audit .env files and scan repositories for leaked secrets" width="100%" />
</p>

<p align="center">
  <strong style="font-size:2rem;color:#22D3EE;">envguard</strong>
</p>
<p align="center">
  <em style="font-size:1.15rem;color:#94A3B8;">Stop secrets before they reach production.</em>
</p>

<p align="center">
  <a href="https://honeyamn10-source.github.io/envguard/"><img src="https://img.shields.io/badge/Website-honeyamn10--source.github.io%2Fenvguard-22D3EE?style=for-the-badge&logo=githubpages&logoColor=white" alt="Website"/></a>
  <a href="https://github.com/honeyamn10-source/envguard/actions"><img src="https://img.shields.io/github/actions/workflow/status/honeyamn10-source/envguard/ci.yml?style=for-the-badge&logo=github" alt="CI"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-34D399?style=for-the-badge" alt="MIT license"/></a>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.9+"/>
  <img src="https://img.shields.io/badge/runtime%20dependencies-0-brightgreen?style=flat-square" alt="Zero runtime dependencies"/>
  <img src="https://img.shields.io/badge/detectors-14-22D3EE?style=flat-square" alt="14 detectors"/>
  <img src="https://img.shields.io/badge/pre--commit-2%20hooks-F59E0B?style=flat-square" alt="pre-commit hooks"/>
</p>

**envguard** is a zero-dependency Python CLI that:

- **lints `.env` files** against their `.env.example` (`envguard check`), and
- **scans entire repositories** for leaked secrets (`envguard scan`).

It runs entirely on your machine with no runtime dependencies and never prints a
full secret — findings are masked by default.

[Website](https://honeyamn10-source.github.io/envguard/) · [Documentation](https://github.com/honeyamn10-source/envguard/tree/main/docs) · [Quick start](#quick-start) · [Security](https://github.com/honeyamn10-source/envguard/blob/main/SECURITY.md)

---

## Quick Start

```bash
git clone https://github.com/honeyamn10-source/envguard.git
cd envguard
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

```bash
# Lint the current .env against .env.example
envguard check .

# Scan the whole repository for leaked secrets
envguard scan .
```

`check` and `scan` both return a CI-friendly exit code: `0` clean, `1` issues
found, `2` usage or I/O error.

---

## The two commands

### `envguard check` — environment file linting

Compares the real `.env` against `.env.example` and reports:

- missing keys (declared in the example but absent),
- extra keys not covered by `--allow`,
- duplicate keys (last value wins),
- quoted/unquoted values that contain `#` or spaces and may break dotenv parsing,
- keys commented out on a comment-only line,
- malformed lines and invalid key names,
- required keys with empty values.

Flags: `--example PATH` · `--allow KEY` (repeatable) · `--require KEY`
(repeatable) · `--strict` (promote warnings to errors) · `--json`.

### `envguard scan` — repository secret scanning

Walks a file or tree, respecting `.gitignore`, `.git/info/exclude`, nested
`.gitignore` files and a root `.envguard-ignore`, then reports findings per line
in `path:line:severity:detector:description` form.

14 built-in detectors:

| Severity | Detectors |
|---|---|
| critical | AWS Access Key ID, AWS Secret Access Key, Stripe secret key, private key material |
| high | GitHub PAT, Slack token, OpenAI API key, PostgreSQL / Redis / MySQL / MongoDB connection strings, JWT |
| medium | high-entropy hex, high-entropy base64 (next to a credential key) |

Flags: `--format human|json` · `--severity LEVELS` · `--max-findings N`.

## Detection quality

- **Entropy gating** — generic hex/base64 candidates must clear a length floor
  and two independent entropy gates (Shannon entropy + length-weighted score).
- **Placeholder-aware** — `<...>`, `changeme`, `YOUR_KEY_HERE`, `example`,
  `****` and similar template values are never reported.
- **Masked findings** — a secret is displayed as `AKIA****ABCD`; export via
  `--json` still contains the masked preview only.
- **Suppression** — `.envguard-ignore` supports whole-file and
  `glob:detector`-specific suppressions.

## pre-commit

Add the bundled hooks to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/honeyamn10-source/envguard
    rev: v0.1.0
    hooks:
      - id: envguard-check   # lint .env files
      - id: envguard-scan    # scan the staged tree
```

## Security

- No network calls; the scanner never transmits scanned content.
- Findings are masked by default so logs and CI output stay clean.
- Zero runtime dependencies (Python standard library only).
- Vulnerabilities: private reporting via
  [security advisory](https://github.com/honeyamn10-source/envguard/security/advisories/new)
  — see [SECURITY.md](https://github.com/honeyamn10-source/envguard/blob/main/SECURITY.md).

## Architecture

```
cli.py        argparse entry point, path resolution, exit-code contract
 └─ check.py  dotenv parser + example comparison → CheckIssue[]
 └─ scan.py   os.walk traversal, binary/1MB guards → ScanResult
     ├─ ignore.py  gitignore-style matcher + .envguard-ignore parsing
     └─ rules.py   14 detectors, placeholder recognition, secret masking
         └─ entropy.py  Shannon entropy + weighted score
output.py     human and JSON formatters
```

Architectural decisions are recorded in
[`docs/decisions/`](https://github.com/honeyamn10-source/envguard/tree/main/docs/decisions).

## Development

```bash
python -m pytest tests -q   # 145 tests across 6 test modules
```

CI runs the suite on Python 3.9–3.13 plus a CLI smoke test that scans the
repository's own source tree.

## License

MIT © 2026 Bittu Sharma