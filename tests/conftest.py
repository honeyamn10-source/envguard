"""Shared pytest fixtures for the envguard test-suite."""

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _slack_token():
    return "xox" "b-1234567890" + "-1234567890-" + "abcdefghijklmnop"


def _stripe_key():
    return "sk_" "live_" + "abcd1234abcd1234abcd1234"


def write_tree(root: "object", files: "dict") -> "object":
    """Write a mapping of relative paths to text content under a root.

    Args:
        root: The directory to populate.
        files: Mapping of relative path to file content.

    Returns:
        The root directory.
    """
    for relpath, content in files.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


@pytest.fixture
def make_tree():
    """Fixture returning a factory that writes a file tree and returns it."""

    def _make(root, files):
        return write_tree(root, files)

    return _make


@pytest.fixture
def fixtures():
    """Path to the static test fixtures directory."""
    return FIXTURES


@pytest.fixture
def scanner_fixture(fixtures, tmp_path):
    """Path to the planted scanner fixture repository.

    The fake Slack and Stripe credentials are injected at runtime, never
    committed, so the repository stays clean for GitHub's own secret scan.
    """
    root = tmp_path / "scanner"
    shutil.copytree(fixtures / "scanner", root)
    env_file = root / "config" / "settings.env"
    content = env_file.read_text()
    content = content.replace("xoxb-replaced-by-runtime", _slack_token())
    content = content.replace("sk_live_replaced_by_runtime", _stripe_key())
    env_file.write_text(content)
    return root