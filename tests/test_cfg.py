"""tests/test_cfg.py — Unit tests for cfg.py (settings load/save/recovery)."""

import json
import os
import sys
import tempfile
import pytest

# Make parent directory importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import cfg


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    """Redirect SETTINGS_FILE to a temporary path for each test."""
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(cfg, "SETTINGS_FILE", str(settings))
    return settings


# ── load_cfg ──────────────────────────────────────────────────────────────────

def test_load_cfg_defaults_when_no_file(tmp_settings):
    result = cfg.load_cfg()
    assert result["opacity"]       == cfg.DEFAULT_CFG["opacity"]
    assert result["update_ms"]     == cfg.DEFAULT_CFG["update_ms"]
    assert result["active_sensors"] == cfg.DEFAULT_CFG["active_sensors"]


def test_load_cfg_reads_saved_values(tmp_settings):
    data = dict(cfg.DEFAULT_CFG)
    data["opacity"] = 55
    data["update_ms"] = 2000
    tmp_settings.write_text(json.dumps(data))

    result = cfg.load_cfg()
    assert result["opacity"]   == 55
    assert result["update_ms"] == 2000


def test_load_cfg_unknown_sensors_filtered(tmp_settings):
    data = dict(cfg.DEFAULT_CFG)
    data["active_sensors"] = ["fps", "nonexistent_sensor"]
    tmp_settings.write_text(json.dumps(data))

    result = cfg.load_cfg()
    assert "nonexistent_sensor" not in result["active_sensors"]
    assert "fps" in result["active_sensors"]


def test_load_cfg_corrupt_json_falls_back_to_defaults(tmp_settings):
    tmp_settings.write_text("{ this is not valid json !!!")

    result = cfg.load_cfg()
    assert result["opacity"] == cfg.DEFAULT_CFG["opacity"]


def test_load_cfg_corrupt_json_creates_backup(tmp_settings):
    tmp_settings.write_text("{ bad json")

    cfg.load_cfg()

    # Original file should be gone; a .corrupt_ backup should exist
    assert not tmp_settings.exists()
    backups = list(tmp_settings.parent.glob("settings.json.corrupt_*"))
    assert len(backups) == 1


# ── save_cfg ──────────────────────────────────────────────────────────────────

def test_save_cfg_writes_file(tmp_settings):
    data = dict(cfg.DEFAULT_CFG)
    data["opacity"] = 77
    cfg.save_cfg(data)

    assert tmp_settings.exists()
    saved = json.loads(tmp_settings.read_text())
    assert saved["opacity"] == 77


def test_save_cfg_no_tmp_leftover(tmp_settings):
    cfg.save_cfg(dict(cfg.DEFAULT_CFG))

    leftover = str(tmp_settings) + ".tmp"
    assert not os.path.exists(leftover)


def test_save_and_reload_roundtrip(tmp_settings):
    original = dict(cfg.DEFAULT_CFG)
    original["opacity"]        = 42
    original["theme"]          = "light"
    original["active_sensors"] = ["fps", "cpu_usage"]
    original["visible"]        = {"fps": True, "cpu_usage": False}

    cfg.save_cfg(original)
    loaded = cfg.load_cfg()

    assert loaded["opacity"]   == 42
    assert loaded["theme"]     == "light"
    assert loaded["active_sensors"] == ["fps", "cpu_usage"]
    assert loaded["visible"]["cpu_usage"] is False


# ── Color helpers ─────────────────────────────────────────────────────────────

def test_default_color_known_sensor():
    color = cfg.default_color("fps")
    assert color.startswith("#")
    assert len(color) == 7


def test_default_color_unknown_sensor():
    color = cfg.default_color("does_not_exist")
    assert color == "#e8e8e8"


def test_eff_color_uses_custom_if_set():
    c = dict(cfg.DEFAULT_CFG)
    c["colors"] = {"fps": "#abcdef"}
    assert cfg.eff_color(c, "fps") == "#abcdef"


def test_eff_color_falls_back_to_default():
    c = dict(cfg.DEFAULT_CFG)
    c["colors"] = {}
    assert cfg.eff_color(c, "fps") == cfg.default_color("fps")
