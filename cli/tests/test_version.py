"""VR1–VR4: version surface + ubds_version compatibility helper."""
import re

from dbf.cli import main
from dbf.schema import BUNDLED_VERSION, load_schema
from dbf.version import check_version


def test_version_prints_cli_version(runner):
    """VR1: `dbf --version` prints a semver-shaped CLI version."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert re.search(r"dbf \d+\.\d+\.\d+", result.output)


def test_version_prints_schema_version(runner):
    """VR2: `dbf --version` reports the bundled UBDS schema version."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert f"UBDS schema v{BUNDLED_VERSION}" in result.output


def test_validate_warns_on_ubds_version_mismatch():
    """VR3: same-major different-minor → warn."""
    level, msg = check_version("1.5")
    assert level == "warn"
    assert msg


def test_validate_errors_on_major_version_mismatch():
    """VR4: different-major → error."""
    level, msg = check_version("2.0")
    assert level == "error"
    assert msg


def test_check_version_ok_on_exact_match():
    level, msg = check_version(BUNDLED_VERSION)
    assert level == "ok"
    assert msg == ""


def test_check_version_errors_on_garbage():
    level, msg = check_version("not-a-version")
    assert level == "error"
    assert msg


def test_load_schema_returns_dict_with_expected_id():
    schema = load_schema()
    assert isinstance(schema, dict)
    assert "$schema" in schema or "properties" in schema
