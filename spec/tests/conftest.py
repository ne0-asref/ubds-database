import json
import pathlib
import pytest
import yaml
from jsonschema import Draft7Validator, FormatChecker

SPEC_DIR = pathlib.Path(__file__).parent.parent
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def schema():
    return json.loads((SPEC_DIR / "ubds-v1.schema.json").read_text())


@pytest.fixture(scope="session")
def validator(schema):
    return Draft7Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def minimal_doc():
    return yaml.safe_load((FIXTURES / "valid-minimal.ubds.yaml").read_text())


def load_fixture(name):
    return yaml.safe_load((FIXTURES / name).read_text())
