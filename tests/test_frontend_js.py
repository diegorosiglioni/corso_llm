"""Runs the tests of the JavaScript of the page with Node's own runner (node --test).

Node.js is needed only as an interpreter for these tests (no npm package); without it the test is
skipped with the reason.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

JS_TESTS = Path(__file__).parent / "frontend"


def test_javascript_of_the_page_with_node():  # CA-82, CA-83
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js non trovato: i test del JavaScript (tests/frontend) non sono eseguiti")
    files = sorted(JS_TESTS.glob("*.test.mjs"))
    assert files, "nessun test in tests/frontend"
    completed = subprocess.run(
        [node, "--test", *[str(path) for path in files]],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "ℹ fail 0" in completed.stdout
