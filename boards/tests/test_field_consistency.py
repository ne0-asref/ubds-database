import pathlib, pytest, warnings, yaml

ROOT = pathlib.Path(__file__).parent.parent.parent
BOARD_DIR = ROOT / "boards"

FRAMEWORK_TO_LANG = {
    "arduino": ["cpp"],
    "espidf": ["c"],
    "cmsis": ["c"],
    "mbed": ["cpp"],
    "stm32cube": ["c"],
    "libopencm3": ["c"],
    "zephyr": ["c"],
    "circuitpython": ["python"],
    "micropython": ["python"],
    "tinygo": ["go"],
    "rust": ["rust"],
    "ardupy": ["python"],
    "fsp": ["c"],
}

BOARD_PATHS = sorted(BOARD_DIR.glob("*.ubds.yaml"))
SLUGS = sorted(p.name.replace(".ubds.yaml", "") for p in BOARD_PATHS)


def _load(slug):
    return yaml.safe_load((BOARD_DIR / f"{slug}.ubds.yaml").read_text())


@pytest.mark.parametrize("slug", SLUGS)
def test_languages_derived_from_frameworks(slug):
    doc = _load(slug)
    fws = [f["name"] for f in doc["software"]["frameworks"]]
    expected = set()
    for f in fws:
        for l in FRAMEWORK_TO_LANG.get(f, []):
            expected.add(l)
    actual = {l["name"] for l in doc["software"]["languages"]}
    missing = expected - actual
    assert not missing, f"{slug}: languages missing {missing} (from frameworks {fws})"


@pytest.mark.parametrize("slug", SLUGS)
def test_wireless_keys_present(slug):
    doc = _load(slug)
    assert "wireless" in doc
    assert isinstance(doc["wireless"], list)


@pytest.mark.parametrize("slug", SLUGS)
def test_wireless_protocols_lowercase(slug):
    doc = _load(slug)
    for w in doc.get("wireless", []):
        assert w["protocol"] == w["protocol"].lower()


@pytest.mark.parametrize("slug", SLUGS)
def test_no_can_in_wireless(slug):
    doc = _load(slug)
    for w in doc.get("wireless", []):
        assert w["protocol"] != "can"


@pytest.mark.parametrize("slug", SLUGS)
def test_frameworks_lowercase(slug):
    doc = _load(slug)
    for f in doc["software"]["frameworks"]:
        assert f["name"] == f["name"].lower()


@pytest.mark.parametrize("slug", SLUGS)
def test_languages_lowercase(slug):
    doc = _load(slug)
    for l in doc["software"]["languages"]:
        assert l["name"] == l["name"].lower()


@pytest.mark.parametrize("slug", SLUGS)
def test_tags_count_minimum(slug):
    doc = _load(slug)
    assert len(doc["tags"]) >= 3


@pytest.mark.parametrize("slug", SLUGS)
def test_use_cases_count_minimum(slug):
    doc = _load(slug)
    assert len(doc["use_cases"]) >= 2


@pytest.mark.parametrize("slug", SLUGS)
def test_form_factor_present(slug):
    doc = _load(slug)
    ff = doc["physical"]["form_factor"]
    assert isinstance(ff, list) and len(ff) >= 1


@pytest.mark.parametrize("slug", SLUGS)
def test_no_pricing_block_or_valid(slug):
    doc = _load(slug)
    if "pricing" in doc:
        assert doc["pricing"]["msrp_usd"] > 0


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_notes_when_msrp_missing(slug):
    doc = _load(slug)
    if "pricing" not in doc:
        if not doc.get("meta", {}).get("notes"):
            warnings.warn(f"{slug}: no pricing and no meta.notes explaining why")
