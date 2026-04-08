import pathlib, pytest, yaml

ROOT = pathlib.Path(__file__).parent.parent.parent
BOARD_DIR = ROOT / "boards"

EXPECTED_BOARDS = {
    "esp32-s3-devkitc-1":               ("Espressif Systems",        ["MCU"]),
    "xiao-esp32-c3":                    ("Seeed Studio",             ["MCU"]),
    "rp2040-pico":                      ("Raspberry Pi Ltd",         ["MCU"]),
    "nrf52840-dk":                      ("Nordic Semiconductor",     ["MCU"]),
    "nucleo-f446re":                    ("STMicroelectronics",       ["MCU"]),
    "nucleo-h743zi":                    ("STMicroelectronics",       ["MCU"]),
    "feather-m0":                       ("Adafruit Industries",      ["MCU"]),
    "feather-m4-express":               ("Adafruit Industries",      ["MCU"]),
    "mimxrt1060-evk":                   ("NXP Semiconductors",       ["MCU"]),
    "arduino-uno-r4-wifi":              ("Arduino",                  ["MCU"]),
    "seeed-wio-terminal":               ("Seeed Studio",             ["MCU"]),
    "blackpill-f411ce":                 ("WeAct Studio",             ["MCU"]),
    "particle-boron":                   ("Particle Industries",      ["MCU"]),
    "adafruit-itsybitsy-m4":            ("Adafruit Industries",      ["MCU"]),
    "adafruit-feather-nrf52840-sense":  ("Adafruit Industries",      ["MCU"]),
}


def _slug(p):
    return p.name.replace(".ubds.yaml", "")


def _load(slug):
    return yaml.safe_load((BOARD_DIR / f"{slug}.ubds.yaml").read_text())


BOARD_PATHS = sorted(BOARD_DIR.glob("*.ubds.yaml"))
SLUGS = sorted(EXPECTED_BOARDS.keys())


def test_every_expected_slug_exists():
    found = {_slug(p) for p in BOARD_PATHS}
    assert set(EXPECTED_BOARDS.keys()) == found


def test_no_unexpected_slugs():
    found = {_slug(p) for p in BOARD_PATHS}
    extras = found - set(EXPECTED_BOARDS.keys())
    assert not extras, f"Unexpected slugs: {extras}"


@pytest.mark.parametrize("slug", SLUGS)
def test_slug_in_yaml_matches_filename(slug):
    doc = _load(slug)
    assert doc["slug"] == slug


@pytest.mark.parametrize("slug", SLUGS)
def test_manufacturer_matches_locked_value(slug):
    doc = _load(slug)
    assert doc["manufacturer"] == EXPECTED_BOARDS[slug][0]


@pytest.mark.parametrize("slug", SLUGS)
def test_board_type_matches_locked_value(slug):
    doc = _load(slug)
    assert doc["board_type"] == EXPECTED_BOARDS[slug][1]


@pytest.mark.parametrize("slug", SLUGS)
def test_ubds_version_is_v1(slug):
    doc = _load(slug)
    assert doc["ubds_version"].startswith("1.")


@pytest.mark.parametrize("slug", SLUGS)
def test_last_verified_is_2026_04_07(slug):
    doc = _load(slug)
    assert doc["meta"]["last_verified"] == "2026-04-07"


@pytest.mark.parametrize("slug", SLUGS)
def test_data_completeness_is_partial(slug):
    doc = _load(slug)
    assert doc["meta"]["data_completeness"] == "partial"
