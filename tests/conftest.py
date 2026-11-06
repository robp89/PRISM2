import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def leach(tmp_path):
    """A writable copy of the leach worked example (without build outputs)."""
    dst = tmp_path / "leach-demo"
    shutil.copytree(ROOT / "examples" / "leach-demo", dst, ignore=shutil.ignore_patterns("build"))
    return dst


@pytest.fixture
def smelt(tmp_path):
    dst = tmp_path / "smelt-screening"
    shutil.copytree(ROOT / "examples" / "smelt-screening", dst, ignore=shutil.ignore_patterns("build"))
    return dst
