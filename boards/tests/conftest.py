import json, pathlib, pytest, yaml
from jsonschema import Draft7Validator, FormatChecker

ROOT = pathlib.Path(__file__).parent.parent.parent

@pytest.fixture(scope="session")
def schema():
    return json.loads((ROOT / "spec" / "ubds-v1.schema.json").read_text())

@pytest.fixture(scope="session")
def validator(schema):
    return Draft7Validator(schema, format_checker=FormatChecker())

@pytest.fixture(scope="session")
def board_paths():
    return sorted((ROOT / "boards").glob("*.ubds.yaml"))

@pytest.fixture(scope="session")
def boards(board_paths):
    return {p.stem.replace(".ubds", ""): yaml.safe_load(p.read_text()) for p in board_paths}
