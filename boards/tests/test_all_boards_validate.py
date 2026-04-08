import json, pathlib, pytest, yaml
from jsonschema import Draft7Validator, FormatChecker

ROOT = pathlib.Path(__file__).parent.parent.parent
SCHEMA = json.loads((ROOT / "spec" / "ubds-v1.schema.json").read_text())
VALIDATOR = Draft7Validator(SCHEMA, format_checker=FormatChecker())
BOARDS = sorted((ROOT / "boards").glob("*.ubds.yaml"))


def _id(p):
    return p.name.replace(".ubds.yaml", "")


@pytest.mark.parametrize("board_path", BOARDS, ids=_id)
def test_board_validates(board_path):
    doc = yaml.safe_load(board_path.read_text())
    errors = list(VALIDATOR.iter_errors(doc))
    assert not errors, f"{board_path.name}: " + "; ".join(
        f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors
    )


def test_board_count():
    assert len(BOARDS) == 15, f"Expected 15 boards, found {len(BOARDS)}"


def test_no_unknown_files_in_boards_dir():
    """boards/ should contain only *.ubds.yaml files + README.md + tests/."""
    allowed = {p.name for p in BOARDS} | {"README.md", "tests"}
    actual = {p.name for p in (ROOT / "boards").iterdir()}
    extras = actual - allowed
    assert not extras, f"Unexpected files in boards/: {extras}"
