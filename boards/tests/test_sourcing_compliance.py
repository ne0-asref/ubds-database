import json, pathlib, pytest, yaml
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).parent.parent.parent
BOARD_DIR = ROOT / "boards"
FIXTURE = json.loads((pathlib.Path(__file__).parent / "fixtures" / "pio_url_hosts.json").read_text())

SLUGS = sorted(FIXTURE.keys())


def _load(slug):
    return yaml.safe_load((BOARD_DIR / f"{slug}.ubds.yaml").read_text())


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_sources_count_is_two(slug):
    doc = _load(slug)
    assert len(doc["meta"]["sources"]) == 2


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_sources_are_distinct(slug):
    doc = _load(slug)
    s = doc["meta"]["sources"]
    assert s[0] != s[1]


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_sources_are_uris(slug):
    doc = _load(slug)
    for url in doc["meta"]["sources"]:
        p = urlparse(url)
        assert p.scheme in {"http", "https"}, url
        assert p.netloc, url


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_sources_first_is_pio_url(slug):
    doc = _load(slug)
    src0 = doc["meta"]["sources"][0]
    host = urlparse(src0).netloc.lower()
    allowed = FIXTURE[slug]
    assert host in allowed, f"{slug}: source[0] host {host} not in allowed {allowed}"


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_confidence_present(slug):
    doc = _load(slug)
    assert "confidence" in doc["meta"]
    assert len(doc["meta"]["confidence"]) >= 1


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_confidence_processing_high(slug):
    doc = _load(slug)
    assert doc["meta"]["confidence"].get("processing") == "high"


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_confidence_software_high(slug):
    doc = _load(slug)
    assert doc["meta"]["confidence"].get("software") == "high"


@pytest.mark.parametrize("slug", SLUGS)
def test_meta_confidence_wireless_high_when_present(slug):
    doc = _load(slug)
    if doc.get("wireless"):
        assert doc["meta"]["confidence"].get("wireless") == "high"
