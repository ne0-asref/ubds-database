"""Shared pytest fixtures for the dbf test suite."""
import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path, monkeypatch):
    """Every test gets its own DBF_CACHE_DIR so nothing pollutes ~/.devboardfinder/."""
    cache_dir = tmp_path / "dbf-cache"
    cache_dir.mkdir()
    monkeypatch.setenv("DBF_CACHE_DIR", str(cache_dir))
