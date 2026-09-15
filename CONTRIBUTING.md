# Contributing

Thanks for taking the time to contribute to `envguard`! 🎉

## Before you start

- Read the [README](README.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
- Check the [issues](https://github.com/honeyamn10-source/envguard/issues) for an
  existing discussion before opening a new one.
- This project targets **Python 3.9+** and is **standard library only** — pull
  requests that add third-party runtime dependencies will be gently rejected.

## Development setup

```console
$ git clone https://github.com/honeyamn10-source/envguard.git
$ cd envguard
$ python -m venv .venv && source .venv/bin/activate
$ pip install -e .
$ pip install pytest
$ pytest tests -q
```

## Making changes

1. Create a branch: `git checkout -b feat/my-change`.
2. Make your change. Follow the existing style:
   - Black formatting (4-space indent, double quotes).
   - Type hints on all public functions.
   - Google-style docstrings only (no inline comments).
3. Add or update tests for any new behaviour. We keep a test per builtin
   detector, per lint check and per ignore semantics — keep it that way.
4. Run the full suite and make sure it is green:

```console
$ pytest tests -q
```

5. Update `CHANGELOG.md` under `[Unreleased]`.
6. Commit with a descriptive message and open a pull request using the
   [template](.github/pull_request_template.md).

## Testing tips

- New detectors need a matching `Rule` in `envguard/rules.py`, a plant in the
  scanner tests, and a row in the README rules table.
- Entropy-based detectors must include a false-positive test (a low-entropy
  token on a credential-like line) as well as a positive one.
- CLI exit codes are part of the contract: verify them in `tests/test_cli.py`.

## Code of conduct

Be kind, be constructive, and assume good faith. Participants must follow the
[Code of Conduct](CODE_OF_CONDUCT.md) in all project spaces.