"""Tests for `dbf import platformio` (IM1–IM15)."""
from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from dbf.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
ESP32 = FIXTURES / "pio_esp32_s3.json"
NUCLEO = FIXTURES / "nucleo_f446re.json"
PIO_DIR = FIXTURES / "pio_dir"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def test_import_single_file_writes_yaml(runner, tmp_path):
    r = runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    out = tmp_path / "pio-esp32-s3.ubds.yaml"
    assert out.exists()


def test_import_output_is_valid_yaml(runner, tmp_path):
    r = runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    data = _load_yaml(tmp_path / "pio-esp32-s3.ubds.yaml")
    assert isinstance(data, dict)
    assert data["ubds_version"] == "1.0"


def test_import_sets_data_completeness_stub(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    data = _load_yaml(tmp_path / "pio-esp32-s3.ubds.yaml")
    assert data["meta"]["data_completeness"] == "stub"


def test_import_sets_one_source(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    data = _load_yaml(tmp_path / "pio-esp32-s3.ubds.yaml")
    sources = data["meta"]["sources"]
    assert isinstance(sources, list)
    assert len(sources) == 1
    assert sources[0] == "https://www.espressif.com/en/products/devkits/esp32-s3-devkitc-1"


def test_import_maps_pio_fields_correctly(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    data = _load_yaml(tmp_path / "pio-esp32-s3.ubds.yaml")
    assert data["name"] == "Espressif ESP32-S3-DevKitC-1"
    assert data["manufacturer"] == "Espressif Systems"
    proc = data["processing"][0]
    assert proc["memory"]["ram_kb"] == 320
    assert proc["memory"]["flash_kb"] == 8192
    core = proc["cpu_cores"][0]
    assert core["architecture"] == "esp32s3"
    assert core["clock_mhz"] == 240
    # PIO doesn't supply core count; importer must not fabricate it.
    assert "count" not in core


def test_import_maps_frameworks(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    data = _load_yaml(tmp_path / "pio-esp32-s3.ubds.yaml")
    names = [f["name"] for f in data["software"]["frameworks"]]
    assert names == ["arduino", "esp-idf"]


def test_import_maps_wireless(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    data = _load_yaml(tmp_path / "pio-esp32-s3.ubds.yaml")
    protos = [w["protocol"] for w in data.get("wireless", [])]
    assert "wifi" in protos
    assert "bluetooth" in protos
    assert "can" not in protos


def test_import_maps_can_to_interfaces(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    data = _load_yaml(tmp_path / "pio-esp32-s3.ubds.yaml")
    assert data["interfaces"]["can"] is True
    protos = [w["protocol"] for w in data.get("wireless", [])]
    assert "can" not in protos


def test_import_directory_mode(runner, tmp_path):
    r = runner.invoke(main, ["import", "platformio", str(PIO_DIR), "--output-dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    files = sorted(tmp_path.glob("*.ubds.yaml"))
    assert len(files) == 3


def test_import_slug_generated_from_filename(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(NUCLEO), "--output-dir", str(tmp_path)])
    assert (tmp_path / "nucleo-f446re.ubds.yaml").exists()


def test_import_collision_appends_suffix(runner, tmp_path):
    runner.invoke(main, ["import", "platformio", str(NUCLEO), "--output-dir", str(tmp_path)])
    runner.invoke(main, ["import", "platformio", str(NUCLEO), "--output-dir", str(tmp_path)])
    assert (tmp_path / "nucleo-f446re.ubds.yaml").exists()
    assert (tmp_path / "nucleo-f446re-imported-2.ubds.yaml").exists()


def test_import_output_dir_default(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Copy fixture into the isolated cwd so it's reachable
        local = Path("esp.json")
        local.write_text(ESP32.read_text())
        r = runner.invoke(main, ["import", "platformio", "esp.json"])
        assert r.exit_code == 0, r.output
        assert Path("imported-boards/esp.ubds.yaml").exists()


def test_import_output_dir_override(runner, tmp_path):
    target = tmp_path / "custom-out"
    r = runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(target)])
    assert r.exit_code == 0, r.output
    assert (target / "pio-esp32-s3.ubds.yaml").exists()


def test_import_summary_printed(runner, tmp_path):
    r = runner.invoke(main, ["import", "platformio", str(ESP32), "--output-dir", str(tmp_path)])
    assert "imported 1" in r.output
    assert "skipped 0" in r.output


def test_import_field_map_module_exists():
    mod = importlib.import_module("dbf.importers.pio_field_map")
    assert hasattr(mod, "map_pio_to_ubds")
