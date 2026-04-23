"""Self-sync drift protection for the canonical board-image vocabulary.

This test module exists because the canonical list of board-image filenames
has three independent homes:

1. ``cli/src/dbf/constants.py``  — ``CANONICAL_IMAGE_FILENAMES`` tuple
   (consumed by the CLI: ``validate --check-images``, ``add-image``,
   ``fetch-images.sh`` pointers).
2. ``spec/ubds-v1.schema.json`` — ``meta.image_filenames.items.enum``
   (informational; schemas cannot validate filesystem contents, but the
   enum advertises the vocabulary to downstream UBDS consumers).
3. ``CONTRIBUTING.md`` + ``templates/minimal.ubds.yaml`` — the human-facing
   contributor docs that board submitters actually read.

If these three ever disagree, contributors get conflicting instructions.
The tests below are the drift alarm.

Two tests — ``test_contributing_names_present`` and
``test_templates_minimal_reminder`` — are ``@pytest.mark.skip``-ed in this
component's branch (C21.1) because the docs + template edits they check
are owned by a later component in the same cycle (C21.6). When C21.6
merges, whoever merges it is responsible for removing the ``@pytest.mark.skip``
decorators. The skip reasons name C21.6 explicitly to make the handoff
obvious.

Run::

    pytest cli/tests/test_canonical_vocab.py -v
"""
import pytest


# ---------- Tier 1: unit (all GREEN on build/C21.1) ----------

def test_canonical_filenames_is_tuple():
    from dbf import constants
    assert isinstance(constants.CANONICAL_IMAGE_FILENAMES, tuple)


def test_canonical_filenames_complete_set():
    from dbf.constants import CANONICAL_IMAGE_FILENAMES
    assert set(CANONICAL_IMAGE_FILENAMES) == {
        "top-view", "pinout", "angle", "bottom-view", "block-diagram"
    }
    assert len(CANONICAL_IMAGE_FILENAMES) == 5


def test_image_fallbacks_set():
    from dbf.constants import IMAGE_FALLBACKS, CANONICAL_IMAGE_FILENAMES
    assert isinstance(IMAGE_FALLBACKS, tuple)
    assert set(IMAGE_FALLBACKS) == {"angle", "bottom-view", "block-diagram"}
    # Consistency invariant: fallbacks + the two non-fallback slots
    # (top-view is the primary; pinout is its own distinct asset) reconstruct
    # the full canonical set exactly.
    assert set(IMAGE_FALLBACKS) | {"top-view", "pinout"} == set(CANONICAL_IMAGE_FILENAMES)


def test_max_image_bytes():
    from dbf.constants import MAX_IMAGE_BYTES
    assert MAX_IMAGE_BYTES == 1_048_576
    assert isinstance(MAX_IMAGE_BYTES, int)


def test_url_pattern_matches_top_view():
    from dbf.constants import CANONICAL_IMAGE_URL_PATTERN
    m = CANONICAL_IMAGE_URL_PATTERN.match(
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/rp2040-pico/top-view.png"
    )
    assert m is not None


def test_url_pattern_rejects_non_canonical():
    from dbf.constants import CANONICAL_IMAGE_URL_PATTERN
    assert CANONICAL_IMAGE_URL_PATTERN.match("https://example.com/image.png") is None
    # github.com/<org>/<repo>/raw/... is a redirect to raw.githubusercontent.com
    # but is NOT the canonical form. Only raw.githubusercontent.com/... matches.
    assert CANONICAL_IMAGE_URL_PATTERN.match(
        "https://github.com/ne0-asref/ubds-database/raw/main/images/foo/top-view.png"
    ) is None


def test_url_pattern_captures_slug():
    from dbf.constants import CANONICAL_IMAGE_URL_PATTERN
    m = CANONICAL_IMAGE_URL_PATTERN.match(
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/rp2040-pico/pinout.png"
    )
    assert m is not None
    assert m.group("slug") == "rp2040-pico"


def test_url_pattern_rejects_query_string():
    from dbf.constants import CANONICAL_IMAGE_URL_PATTERN
    assert CANONICAL_IMAGE_URL_PATTERN.match(
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/rp2040-pico/top-view.png?v=1"
    ) is None


def test_url_pattern_rejects_trailing_slash():
    from dbf.constants import CANONICAL_IMAGE_URL_PATTERN
    assert CANONICAL_IMAGE_URL_PATTERN.match(
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/rp2040-pico/top-view.png/"
    ) is None


def test_url_pattern_rejects_uppercase_slug():
    from dbf.constants import CANONICAL_IMAGE_URL_PATTERN
    assert CANONICAL_IMAGE_URL_PATTERN.match(
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/RP2040-Pico/top-view.png"
    ) is None
    # Also reject leading hyphen — slug pattern requires [a-z0-9] as the first char.
    assert CANONICAL_IMAGE_URL_PATTERN.match(
        "https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/-pico/top-view.png"
    ) is None


def test_png_signature():
    from dbf.constants import PNG_SIGNATURE
    assert PNG_SIGNATURE == b"\x89PNG\r\n\x1a\n"
    assert len(PNG_SIGNATURE) == 8


def test_png_ihdr_color_type_rgba():
    from dbf.constants import PNG_IHDR_COLOR_TYPE_RGBA
    assert PNG_IHDR_COLOR_TYPE_RGBA == 6


# ---------- Tier 2: integration (drift protection) ----------

def test_schema_enum_matches_constants():
    import json
    from pathlib import Path
    from dbf.constants import CANONICAL_IMAGE_FILENAMES

    schema_path = (
        Path(__file__).resolve().parent.parent.parent
        / "spec" / "ubds-v1.schema.json"
    )
    with schema_path.open() as f:
        schema = json.load(f)

    enum = schema["properties"]["meta"]["properties"]["image_filenames"]["items"]["enum"]

    assert sorted(enum) == sorted(CANONICAL_IMAGE_FILENAMES), (
        f"Schema enum {sorted(enum)} != CLI constant {sorted(CANONICAL_IMAGE_FILENAMES)} — "
        "update spec/ubds-v1.schema.json::meta.properties.image_filenames.items.enum "
        "or cli/src/dbf/constants.py::CANONICAL_IMAGE_FILENAMES."
    )


def test_changelog_has_image_filenames_entry():
    from pathlib import Path

    changelog_path = (
        Path(__file__).resolve().parent.parent.parent
        / "spec" / "CHANGELOG.md"
    )
    text = changelog_path.read_text()
    assert "image_filenames" in text, (
        "spec/CHANGELOG.md is missing an entry that mentions `image_filenames` — "
        "add an additive entry naming the new meta.image_filenames schema field."
    )


# The next two tests check cross-file drift against CONTRIBUTING.md and
# templates/minimal.ubds.yaml — files that land in C21.6. They are skipped
# until then. When C21.6 merges, remove the @pytest.mark.skip decorator
# from each (this is called out in C21.6's spec as part of its DONE
# criteria). See module docstring.

@pytest.mark.skip(
    reason="CONTRIBUTING.md §Adding a board image section is C21.6 territory; "
           "unskip when that component merges."
)
def test_contributing_names_present():
    from pathlib import Path
    from dbf.constants import CANONICAL_IMAGE_FILENAMES

    contributing_path = (
        Path(__file__).resolve().parent.parent.parent / "CONTRIBUTING.md"
    )
    text = contributing_path.read_text()

    section_start = text.find("## Adding a board image")
    assert section_start != -1, (
        "CONTRIBUTING.md is missing '## Adding a board image' section"
    )
    section_end = text.find("\n## ", section_start + 1)
    if section_end == -1:
        section_end = len(text)
    section = text[section_start:section_end]

    missing = [name for name in CANONICAL_IMAGE_FILENAMES if name not in section]
    assert not missing, (
        f"CONTRIBUTING.md §Adding a board image does not mention: {missing}"
    )


@pytest.mark.skip(
    reason="templates/minimal.ubds.yaml canonical-filenames reminder is C21.6 territory; "
           "unskip when that component merges."
)
def test_templates_minimal_reminder():
    from pathlib import Path
    from dbf.constants import CANONICAL_IMAGE_FILENAMES

    minimal_path = (
        Path(__file__).resolve().parent.parent.parent
        / "templates" / "minimal.ubds.yaml"
    )
    text = minimal_path.read_text()
    missing = [name for name in CANONICAL_IMAGE_FILENAMES if name not in text]
    assert not missing, (
        f"templates/minimal.ubds.yaml missing canonical filenames: {missing}"
    )
