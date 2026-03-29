"""tests/test_hw.py — Unit tests for hw.py (sensor picking, fallback logic)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import hw
from cfg import SENSOR_CATALOG, active_sensor_defs, DEFAULT_CFG

# read_mahm() now returns {name: (val, max_val)} tuples
_RAW_ONE   = {"gpu1 usage": (78.5, 90.0), "cpu usage": (42.0, 55.0)}
_RAW_TEMP  = {"gpu1 temperature value": (65.0, 80.0)}
_RAW_MULTI = {"gpu1 usage": (90.0, 95.0), "gpu usage": (85.0, 88.0)}
_RAW_FPS   = {"framerate": (120.0, 144.0)}
_RAW_OTHER = {"some_other_sensor": (1.0, 1.0)}


# ── _pick_sensor ──────────────────────────────────────────────────────────────

def test_pick_sensor_exact_match():
    val, mx = hw._pick_sensor(_RAW_ONE, ("gpu1 usage",))
    assert val == pytest.approx(78.5)
    assert mx  == pytest.approx(90.0)


def test_pick_sensor_substring_match():
    val, mx = hw._pick_sensor(_RAW_TEMP, ("gpu1 temperature",))
    assert val == pytest.approx(65.0)
    assert mx  == pytest.approx(80.0)


def test_pick_sensor_first_candidate_wins():
    val, mx = hw._pick_sensor(_RAW_MULTI, ("gpu1 usage", "gpu usage"))
    assert val == pytest.approx(90.0)
    assert mx  == pytest.approx(95.0)


def test_pick_sensor_returns_none_when_no_match():
    val, mx = hw._pick_sensor(_RAW_OTHER, ("framerate",))
    assert val is None
    assert mx  is None


def test_pick_sensor_empty_raw():
    val, mx = hw._pick_sensor({}, ("framerate",))
    assert val is None
    assert mx  is None


# ── get_data fallback for Windows-API sensors ─────────────────────────────────

def test_get_data_ram_fallback(monkeypatch):
    """RAM sensor should use Windows API fallback even when MAHM is empty."""

    monkeypatch.setattr(hw, "read_mahm", lambda: {})

    cfg = dict(DEFAULT_CFG)
    cfg["active_sensors"] = ["ram_usage"]
    cfg["visible"]        = {"ram_usage": True}
    sensors = active_sensor_defs(cfg)

    data, maxes, src = hw.get_data(sensors)

    assert "ram_usage" in data
    assert data["ram_usage"] is not None
    assert 0 <= data["ram_usage"] <= 100
    assert maxes["ram_usage"] == SENSOR_CATALOG["ram_usage"].bar_max
    assert src == "N/A"


def test_get_data_mahm_sensor_missing_returns_none(monkeypatch):
    """When MAHM is running but doesn't have a sensor, return None."""

    monkeypatch.setattr(hw, "read_mahm", lambda: _RAW_OTHER)

    cfg = dict(DEFAULT_CFG)
    cfg["active_sensors"] = ["fps"]
    cfg["visible"]        = {"fps": True}
    sensors = active_sensor_defs(cfg)

    data, maxes, src = hw.get_data(sensors)

    assert data["fps"] is None
    assert maxes["fps"] is None
    assert src == "MSI Afterburner"


def test_get_data_source_label_when_mahm_unavailable(monkeypatch):
    monkeypatch.setattr(hw, "read_mahm", lambda: {})

    cfg = dict(DEFAULT_CFG)
    cfg["active_sensors"] = ["fps"]
    cfg["visible"]        = {"fps": True}
    sensors = active_sensor_defs(cfg)

    _, _mx, src = hw.get_data(sensors)
    assert src == "N/A"


def test_get_data_source_label_when_mahm_available(monkeypatch):
    monkeypatch.setattr(hw, "read_mahm", lambda: _RAW_FPS)

    cfg = dict(DEFAULT_CFG)
    cfg["active_sensors"] = ["fps"]
    cfg["visible"]        = {"fps": True}
    sensors = active_sensor_defs(cfg)

    data, maxes, src = hw.get_data(sensors)
    assert src == "MSI Afterburner"
    assert data["fps"]  == pytest.approx(120.0)
    assert maxes["fps"] == pytest.approx(144.0)
