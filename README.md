# envguard

Audit your `.env` files and scan your codebase for leaked secrets — before it's too late.

[![GitHub stars](https://img.shields.io/github/stars/honeyamn10-source/envguard?style=flat-square)](https://github.com/honeyamn10-source/envguard/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/honeyamn10-source/envguard?style=flat-square)](https://github.com/honeyamn10-source/envguard/network)
[![Python version](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

`envguard` is a fast, dependency-free command-line tool with two jobs:

1. **`envguard check`** — lint your `.env` files against a `.env.example` so config drift, empty required values and quoting foot-guns are caught in review.
2. **`envguard scan`** — walk a Git repository looking for credentials that should never be committed: AWS keys, GitHub PATs, Stripe/OpenAI keys, JWTs, connection strings with passwords and high-entropy secrets.

Pure **Python 3.9+ standard library only**. No third-party imports, no lockfiles, no install-size anxiety — install it anywhere a Python interpreter exists.

```
$ envguard
usage: envguard [-h] [--version] command ...

Audit your .env files and scan your codebase for leaked secrets before it's too late.

positional arguments:
  command
    check     Lint a .env file against a .env.example file
    scan      Scan a codebase for leaked secrets
```

## Table of contents

- [Why envguard](#why-envguard)
- [Install](#install)
- [Quick start](#quick-start)
- [Usage](#usage)
  - [check: lint .env files](#check-lint-env-files)
  - [scan: find leaked secrets](#scan-find-leaked-secrets)
- [Builtin rules](#builtin-rules)
- [Configuration](#configuration)
- [Exit codes](#exit-codes)
- [CI and pre-commit](#ci-and-pre-commit)
- [Roadmap](#roadmap)
- [License](#license)

## Why envguard

Every secret you commit today becomes a credential you must rotate tomorrow. `envguard` exists to make that workflow painless:

- **Zero dependencies.** It runs on a bare Python interpreter and installs in milliseconds.
- **Low noise.** Entropy gating, placeholder suppression and gitignore awareness keep findings actionable instead of fearsome.
- **Two tools, one binary.** Environment hygiene and secret scanning share the same fast engine.

## Install

```console
$ pip install envguard
```

Or install the latest code in editable mode from a clone, ready for development:

```console
$ git clone https://github.com/honeyamn10-source/envguard.git
$ cd envguard
$ pip install -e .
```

That's it. No extra dependencies are pulled in.

## Quick start

```console
$ envguard check .              # lint .env against .env.example
$ envguard check --strict      # treat warnings as errors
$ envguard scan .              # scan the whole repo for leaked secrets
$ envguard scan . --severity critical,high
$ envguard scan . --format json
```

## Usage

### `envguard check` — lint .env files

`envguard check [path]` expects either a directory containing `.env` and `.env.example`, or an explicit path to a `.env` file. The example file is the source of truth; it can also be supplied with `--example`.

```text
$ envguard check .
checking .env against .env.example
.env:5:warning:duplicate-key:key 'DUPLICATE' appears 2 times; the last value wins
.env:9:error:malformed-line:line contains no '=' separator: 'NOT_A_LINE_this_is_text'
.env:11:warning:unquoted-space:unquoted value for 'LOG_LEVEL' contains spaces and may break dotenv parsing
.env:0:warning:missing-key:key 'REQUIRED_SERVICE' is present in the example but missing from the env file

Summary: 4 issue(s) (3 warning(s), 1 error(s))
```

Detected problems include:

| Finding | Severity |
| --- | --- |
| Missing key (in example, not in env) | warning |
| Extra key (in env, not in example) | warning |
| Duplicate key (last value wins) | warning |
| Unquoted value containing `#` | warning |
| Unquoted value containing spaces | warning |
| Commented-out key (comment-only section) | warning |
| Empty value for a required key | error |
| Malformed line (no `=`, or invalid key name) | error |

Use `--allow KEY` to permit keys that only exist locally (repeatable) and `--require KEY` to force a key to be non-empty even when the example leaves it blank (repeatable). `--strict` upgrades every warning to error severity (the exit code stays `1`). `--json` emits a machine-readable report.

```console
$ envguard check . --allow LOCAL_TOKEN --require DEPLOY_REGION --strict --json
```

### `envguard scan` — find leaked secrets

`envguard scan [path]` climbs the tree from `path` (default `.`), honours `.gitignore`, `.git/info/exclude` and a small builtin ignore list, skips binary and 1MB+ files, and reports findings per line:

```text
$ envguard scan .
scanning /home/you/src/myapp
config/settings.env:2:critical:aws-access-key-id:AWS Access Key ID
config/settings.env:3:critical:aws-secret-access-key:AWS Secret Access Key
config/settings.env:4:high:github-pat:GitHub Personal Access Token
keys/deploy.pem:1:critical:private-key:Private key material

Summary: 4 finding(s) across 23 file(s)
severity  count
----------------
critical      3
high          1
detector            count
--------------------------
aws-access-key-id       1
github-pat              1
private-key             1
aws-secret-access-key   1
```

Options:

```console
$ envguard scan .                      # human output
$ envguard scan . --format json        # machine-readable JSON
$ envguard scan . --severity critical,high
$ envguard scan . --max-findings 20    # stop after 20 findings
```

Secrets are always masked in output (`AKIA****MPLE`), so reports are safe to paste into issue trackers.

## Builtin rules

| Detector | Severity | Description |
| --- | --- | --- |
| `aws-access-key-id` | critical | AWS Access Key ID (`AKIA…`) |
| `aws-secret-access-key` | critical | AWS Secret Access Key |
| `github-pat` | high | GitHub Personal Access Token (`ghp_`, `ghs_`, `ghu_`, `ghr_`, `gho_`, `github_pat_`) |
| `slack-token` | high | Slack API token (`xoxb-`, `xoxa-`, …) |
| `stripe-key` | high | Stripe secret API key (`sk_live_`) |
| `openai-api-key` | high | OpenAI API key (`sk-proj-`, `sk-`) |
| `private-key` | critical | RSA / DSA / EC / OpenSSH / PGP private key material |
| `postgresql-url` | high | PostgreSQL connection string with embedded credentials |
| `redis-url` | high | Redis connection string with embedded password |
| `mysql-url` | high | MySQL connection string with embedded credentials |
| `mongodb-url` | high | MongoDB connection string with embedded credentials |
| `jwt` | high | JSON Web Token (three-segment `eyJ…`) |
| `high-entropy-hex` | medium | 32+ hex characters next to a credential-ish key name |
| `high-entropy-base64` | medium | 32+ base64 characters next to a credential-ish key name |

High-entropy detectors combine a regex with a weighted Shannon entropy heuristic and a key-name hint, so repetitive or dictionary-like strings (and SSH public keys) are not flagged. Placeholder values such as `YOUR_API_KEY_HERE`, `changeme`, `xxxx` or `<put_token_here>` are never reported, and strong platform detectors take precedence over the entropy heuristics to avoid duplicate findings.

## Configuration

### `.gitignore`

`scan` respects project `.gitignore` files (root and nested), `.git/info/exclude`, and these builtin patterns:

```
.git/  .hg/  .svn/  .venv/  venv/  __pycache__/  node_modules/
dist/  build/  .cache/  .tox/  .eggs/  .mypy_cache/  .pytest_cache/
*.py[cod]  *.egg-info/  *.lock  package-lock.json  yarn.lock
*.min.js  *.min.css  *.map
```

### `.envguard-ignore`

Add a `.envguard-ignore` file at the repository root to silence findings — one glob per line, or `file:detector` to silence a single detector in matching files:

```
# never scan vendored keys, even if they are real
vendor/*.pem

# this file is expected to hold local connection settings
config/local.env:mongodb-url
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. `check`: no problems. `scan`: no findings. |
| `1` | Issues found. `check`: warnings and/or errors. `scan`: leaked secrets. |
| `2` | Usage or runtime error (bad flag, unknown severity, missing path/file). |

## CI and pre-commit

Run `scan` in CI so leaked secrets fail the pipeline before they reach `main`:

```yaml
- name: Scan for leaked secrets
  run: pip install envguard && envguard scan . --severity critical,high
```

As a pre-commit hook, drop the bundled hooks into your `.pre-commit-hooks.yaml` and reference them:

```yaml
repos:
  - repo: https://github.com/honeyamn10-source/envguard
    rev: v0.1.0
    hooks:
      - id: envguard-check
      - id: envguard-scan
```

## Roadmap

- [x] `.env` vs `.env.example` linting
- [x] Builtin secret ruleset with entropy gating
- [x] gitignore / `.envguard-ignore` awareness
- [x] JSON output for both commands
- [ ] `--include` / `--exclude` path overrides
- [ ] GitHub Actions action with SARIF upload
- [ ] Detect keys rotated by known scanners (`nv | jq`)
- [ ] Config file (`envguard.toml`) for custom detection rules
- [ ] `pre-commit` scanned-secret caching for faster hooks

## License

[MIT](LICENSE) © 2026 Bittu Sharma.