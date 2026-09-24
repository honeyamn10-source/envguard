[![Coverage report](https://img.shields.io/github/actions/workflow/status/honeyamn10-source/envguard/coverage.yml?branch=main&label=coverage)](https://github.com/honeyamn10-source/envguard/actions/workflows/coverage.yml)

![envguard — Secrets & environment hygiene](docs/assets/cover.svg)

# envguard

<!-- repo-badges:start -->
<div align="center">

[![Stars](https://img.shields.io/github/stars/honeyamn10-source/envguard?style=flat-square&logo=github&label=Stars)](https://github.com/honeyamn10-source/envguard/stargazers)
[![Forks](https://img.shields.io/github/forks/honeyamn10-source/envguard?style=flat-square&logo=github&label=Forks)](https://github.com/honeyamn10-source/envguard/forks)
[![Issues](https://img.shields.io/github/issues/honeyamn10-source/envguard?style=flat-square&logo=github&label=Issues)](https://github.com/honeyamn10-source/envguard/issues)
[![Last Commit](https://img.shields.io/github/last-commit/honeyamn10-source/envguard?style=flat-square&logo=github&label=Last%20Commit)](https://github.com/honeyamn10-source/envguard/commits/main)

[Repository](https://github.com/honeyamn10-source/envguard) · [Issues](https://github.com/honeyamn10-source/envguard/issues) · [Pull Requests](https://github.com/honeyamn10-source/envguard/pulls) · [Actions](https://github.com/honeyamn10-source/envguard/actions)

</div>
<!-- repo-badges:end -->

<!-- professional-meta:start -->
<div align="center">

[![ci](https://github.com/honeyamn10-source/envguard/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/honeyamn10-source/envguard/actions/workflows/ci.yml) [![codeql](https://github.com/honeyamn10-source/envguard/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/honeyamn10-source/envguard/actions/workflows/codeql.yml) [![coverage](https://github.com/honeyamn10-source/envguard/actions/workflows/coverage.yml/badge.svg?branch=main)](https://github.com/honeyamn10-source/envguard/actions/workflows/coverage.yml)

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white) ![Pre-commit](https://img.shields.io/badge/Pre-commit-FAB040?style=flat-square&logo=precommit&logoColor=white)

[Documentation](docs) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [Live Demo](https://honeyamn10-source.github.io/envguard/)

</div>
<!-- professional-meta:end -->


A small Python CLI for checking environment files and finding likely credentials in a source tree.

[Project website](https://honeyamn10-source.github.io/envguard/) · [Source](https://github.com/honeyamn10-source/envguard) · [Build results](https://github.com/honeyamn10-source/envguard/actions) · [Issues](https://github.com/honeyamn10-source/envguard/issues)

## What it does

- **Check environment files.** Compare .env with .env.example for missing, extra, duplicate and empty required values.
- **Scan the source.** Pattern and entropy checks produce file-and-line findings with severity filters.
- **Use the result.** Human-readable or JSON scan output; documented exit codes for automation.

## Start from source

Python 3.9 or later. No third-party runtime dependencies.

```bash
git clone https://github.com/honeyamn10-source/envguard.git
cd envguard
python -m pip install .
envguard scan . --severity critical,high
envguard check . --strict
```

For an isolated install, create a virtual environment first:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
```

On Windows PowerShell, use `.\.venv\Scripts\Activate.ps1`, or call `.\.venv\Scripts\python.exe` directly if script activation is restricted.

### CLI reference

| Task | Command |
| --- | --- |
| Scan likely secrets | `envguard scan .` |
| Filter severity | `envguard scan . --severity critical,high` |
| JSON scan report | `envguard scan . --format json` |
| Compare environment keys | `envguard check . --example .env.example` |
| Require nonempty key | `envguard check . --require DATABASE_URL` |
| JSON environment report | `envguard check . --json` |

Exit codes: **0** no findings, **1** findings, **2** invalid input or execution error. Scanning respects supported `.gitignore` and `.envguard-ignore` patterns. There is no `config.yaml` or `envguard.toml` loader; configure supported options through CLI flags.

## Check your changes

```bash
python -m pip install pytest
python -m pytest tests -q
```

These are the repository’s checks, not a claim of complete test coverage. See [GitHub Actions](https://github.com/honeyamn10-source/envguard/actions) for the result on a specific commit.

## Scope and limitations

Detection is heuristic. Review findings and rotate any exposed credential. The CLI supports human and JSON scan output; SARIF, JUnit, standalone binaries and Docker images are not supplied here.

## Find your way around

| Source | Purpose |
| --- | --- |
| [`envguard/cli.py`](envguard/cli.py) | CLI and exit codes |
| [`envguard/rules.py`](envguard/rules.py) | Detection rules |
| [`tests/`](tests/) | Regression fixtures and tests |

## Contributing

Include the command you ran, your runtime version, a minimal reproduction and the expected result in an issue. Remove credentials and personal data from logs. Follow [CONTRIBUTING.md](CONTRIBUTING.md) when proposing a change.

## License

MIT — see [LICENSE](LICENSE). Third-party dependencies retain their own licenses.

## Coverage report

The coverage badge shows whether the coverage workflow passes. Open its latest successful run and download `coverage-report` for measured line coverage and uncovered lines. The badge is a workflow status, not a claimed percentage.
