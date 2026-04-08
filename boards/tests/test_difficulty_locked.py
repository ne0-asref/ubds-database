import pathlib, pytest, yaml
from collections import Counter

ROOT = pathlib.Path(__file__).parent.parent.parent
BOARD_DIR = ROOT / "boards"

DIFFICULTY_LOCKED = {
    "esp32-s3-devkitc-1":              "intermediate",
    "xiao-esp32-c3":                   "beginner",
    "rp2040-pico":                     "beginner",
    "nrf52840-dk":                     "intermediate",
    "nucleo-f446re":                   "intermediate",
    "nucleo-h743zi":                   "intermediate",
    "feather-m0":                      "beginner",
    "feather-m4-express":              "beginner",
    "mimxrt1060-evk":                  "advanced",
    "arduino-uno-r4-wifi":             "beginner",
    "seeed-wio-terminal":              "beginner",
    "blackpill-f411ce":                "intermediate",
    "particle-boron":                  "intermediate",
    "adafruit-itsybitsy-m4":           "beginner",
    "adafruit-feather-nrf52840-sense": "intermediate",
}

SLUGS = sorted(DIFFICULTY_LOCKED.keys())


def _load(slug):
    return yaml.safe_load((BOARD_DIR / f"{slug}.ubds.yaml").read_text())


@pytest.mark.parametrize("slug", SLUGS)
def test_difficulty_locked(slug):
    doc = _load(slug)
    assert doc["difficulty_level"] == DIFFICULTY_LOCKED[slug]


def test_distribution_matches_locked_table():
    """Distribution must match the locked table in spec.md §Step 5a verbatim.
    Note: spec.md prose claims 7/6/2 but the locked per-board values sum to
    7 beginner / 7 intermediate / 1 advanced. Per the no-silent-correction rule,
    the per-board lock is authoritative; the prose summary is a known doc bug
    flagged in status.md. Every difficulty level still has >=1 board for the
    frontend filter UI."""
    actual = Counter()
    for slug in SLUGS:
        actual[_load(slug)["difficulty_level"]] += 1
    expected = Counter(DIFFICULTY_LOCKED.values())
    assert actual == expected
    assert actual["beginner"] >= 1
    assert actual["intermediate"] >= 1
    assert actual["advanced"] >= 1
