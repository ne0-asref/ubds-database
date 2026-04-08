import pathlib, pytest, yaml

ROOT = pathlib.Path(__file__).parent.parent.parent
BOARD_DIR = ROOT / "boards"

PROCESSING_LOCKED = {
    "esp32-s3-devkitc-1": [
        {"architecture": "Xtensa LX7", "core_count": 2, "clock_mhz": 240}
    ],
    "xiao-esp32-c3": [
        {"architecture": "RISC-V (RV32IMC)", "core_count": 1, "clock_mhz": 160}
    ],
    "rp2040-pico": [
        {"architecture": "ARM Cortex-M0+", "core_count": 2, "clock_mhz": 133}
    ],
    "nrf52840-dk": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 64}
    ],
    "nucleo-f446re": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 180}
    ],
    "nucleo-h743zi": [
        {"architecture": "ARM Cortex-M7", "core_count": 1, "clock_mhz": 480}
    ],
    "feather-m0": [
        {"architecture": "ARM Cortex-M0+", "core_count": 1, "clock_mhz": 48}
    ],
    "feather-m4-express": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 120}
    ],
    "mimxrt1060-evk": [
        {"architecture": "ARM Cortex-M7", "core_count": 1, "clock_mhz": 600}
    ],
    "arduino-uno-r4-wifi": [
        {"architecture": "ARM Cortex-M4", "core_count": 1, "clock_mhz": 48},
        {"architecture": "Xtensa LX7",   "core_count": 2, "clock_mhz": 240},
    ],
    "seeed-wio-terminal": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 120}
    ],
    "blackpill-f411ce": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 100}
    ],
    "particle-boron": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 64}
    ],
    "adafruit-itsybitsy-m4": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 120}
    ],
    "adafruit-feather-nrf52840-sense": [
        {"architecture": "ARM Cortex-M4F", "core_count": 1, "clock_mhz": 64}
    ],
}

SLUGS = sorted(PROCESSING_LOCKED.keys())


def _load(slug):
    return yaml.safe_load((BOARD_DIR / f"{slug}.ubds.yaml").read_text())


@pytest.mark.parametrize("slug", SLUGS)
def test_processing_entry_count(slug):
    doc = _load(slug)
    assert len(doc["processing"]) == len(PROCESSING_LOCKED[slug])


@pytest.mark.parametrize("slug", SLUGS)
def test_processing_per_entry(slug):
    doc = _load(slug)
    expected = PROCESSING_LOCKED[slug]
    for idx, exp in enumerate(expected):
        entry = doc["processing"][idx]
        cores = entry["cpu_cores"]
        archs = {c["architecture"] for c in cores}
        assert exp["architecture"] in archs, f"{slug}[{idx}]: arch {exp['architecture']} not in {archs}"
        total = sum(c["count"] for c in cores)
        assert total == exp["core_count"], f"{slug}[{idx}]: core_count mismatch {total} != {exp['core_count']}"
        max_clock = max(c["clock_mhz"] for c in cores)
        assert max_clock == exp["clock_mhz"], f"{slug}[{idx}]: clock_mhz mismatch {max_clock} != {exp['clock_mhz']}"


def test_uno_r4_wifi_has_co_processor():
    doc = _load("arduino-uno-r4-wifi")
    assert len(doc["processing"]) == 2
