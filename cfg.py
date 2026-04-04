"""cfg.py — App configuration: constants, settings persistence, Windows startup."""

import sys, os, json, winreg, re
from typing import NamedTuple

from logger import get_logger

_log = get_logger("cfg")

# ── Windows startup registry ──────────────────────────────────────────────────
_STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME    = "Palantir"


def _startup_cmd():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pythonw}" "{os.path.abspath(sys.argv[0])}"'


def is_startup_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_KEY)
        winreg.QueryValueEx(key, _APP_NAME)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def set_startup(enabled):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_KEY, 0, winreg.KEY_SET_VALUE
        )
        if enabled:
            winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _startup_cmd())
        else:
            try:
                winreg.DeleteValue(key, _APP_NAME)
            except OSError:
                pass
        winreg.CloseKey(key)
    except OSError:
        pass


# ── Settings file path ────────────────────────────────────────────────────────
_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "Palantir",
)
os.makedirs(_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(_DIR, "settings.json")


# ── Sensor definitions ────────────────────────────────────────────────────────
class SensorDef(NamedTuple):
    key:        str
    label:      str
    unit:       str
    color:      str
    bar_max:    float
    mahm_names: tuple   # MAHM source-name substrings; empty = Windows API fallback

SENSOR_CATALOG: dict[str, "SensorDef"] = {s.key: s for s in [
    # ── Core sensors (default set) ─────────────────────────────────────────────
    SensorDef("fps",        "FPS",      "",    "#e8e8f8", 360,  ("framerate", "frame rate")),
    SensorDef("fps_1pct",   "FPS 1%",   "",    "#b8c0e8", 360,  ("1% low framerate", "1% low fps", "1% low", "fps 1% low", "framerate 1% low", "frame rate 1%")),
    SensorDef("gpu_usage",  "GPU USE",  "%",   "#6474f0", 100,  ("gpu1 usage",       "gpu usage")),
    SensorDef("gpu_temp",   "GPU TEMP", "°",   "#ef5350", 110,  ("gpu1 temperature", "gpu temperature")),
    SensorDef("gpu_hotspot","GPU HOT",  "°",   "#ff1744", 115,  ("hot spot", "junction temperature", "gpu hot spot", "hotspot", "junction temp", "gpu1 hot spot", "temperature 2")),
    SensorDef("gpu_power",  "GPU PWR",  "W",   "#ff7043", 400,  ("gpu power", "power")),
    SensorDef("gpu_clock",  "GPU CLK",  "MHz", "#b07cf5", 3000, ("core clock", "gpu clock")),
    SensorDef("gpu_fan",    "GPU FAN",  "%",   "#78909c", 100,  ("fan speed", "fan tachometer")),
    SensorDef("vram_usage", "VRAM USE", "%",   "#4f8ef7", 100,  ("fb usage", "vram usage")),
    SensorDef("gpu2_usage", "GPU2 USE", "%",   "#7986cb", 100,  ("gpu2 usage",)),
    SensorDef("cpu_usage",  "CPU USE",  "%",   "#66bb6a", 100,  ("cpu usage", "cpu total")),
    SensorDef("cpu_temp",   "CPU TEMP", "°",   "#ffa726", 110,  ("cpu temperature",)),
    SensorDef("cpu_power",  "CPU PWR",  "W",   "#ffe57f", 350,  ("cpu power", "package power", "cpu package power", "cpu pkg power", "processor power")),
    SensorDef("cpu_clock",  "CPU CLK",  "MHz", "#c8e6c9", 7000, ("cpu clock", "cpu core clock", "core #1 clock", "cpu frequency")),
    SensorDef("ram_usage",  "RAM USE",  "%",   "#9b59f5", 100,  ()),  # Windows API
]}

_DEFAULT_ACTIVE = ["fps", "gpu_usage", "gpu_temp", "cpu_usage", "cpu_temp", "ram_usage"]

DEFAULT_CFG = {
    "opacity":         90,
    "hover_opacity":   20,
    "update_ms":       1000,
    "locked":          False,
    "always_on_top":   True,
    "pos_x":           -1,
    "pos_y":           -1,
    "theme":           "dark",
    "active_sensors":  list(_DEFAULT_ACTIVE),
    "visible":         {k: True for k in _DEFAULT_ACTIVE},
    "colors":          {},
    "skipped_version": "",
}


# ── Settings validation ───────────────────────────────────────────────────────
_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _sanitize_cfg(cfg: dict) -> dict:
    """Clamp/coerce every scalar field so bad values in settings.json can't crash the app."""
    def clamp_int(v, lo, hi, default):
        try:
            v = int(v)
        except (TypeError, ValueError):
            return default
        return max(lo, min(hi, v))

    def valid_color(v, default):
        return v if isinstance(v, str) and _HEX_RE.match(v) else default

    def snap_ms(v):
        opts = [500, 1000, 2000, 5000]
        try:
            v = int(v)
        except (TypeError, ValueError):
            return DEFAULT_CFG["update_ms"]
        return min(opts, key=lambda x: abs(x - v))

    cfg["opacity"]       = clamp_int(cfg["opacity"],       20,  100, DEFAULT_CFG["opacity"])
    cfg["hover_opacity"] = clamp_int(cfg["hover_opacity"],  5,   80, DEFAULT_CFG["hover_opacity"])
    cfg["update_ms"]     = snap_ms(cfg["update_ms"])
    cfg["locked"]        = bool(cfg["locked"])
    cfg["always_on_top"] = bool(cfg["always_on_top"])
    try:
        cfg["pos_x"] = int(cfg["pos_x"])
        cfg["pos_y"] = int(cfg["pos_y"])
    except (TypeError, ValueError):
        cfg["pos_x"] = DEFAULT_CFG["pos_x"]
        cfg["pos_y"] = DEFAULT_CFG["pos_y"]
    cfg["theme"] = cfg.get("theme", "dark") if cfg.get("theme") in ("dark", "light") else "dark"
    cfg["colors"] = {
        k: v for k, v in cfg.get("colors", {}).items()
        if k in SENSOR_CATALOG and isinstance(v, str) and _HEX_RE.match(v)
    }
    return cfg


# ── Load / save ───────────────────────────────────────────────────────────────
def load_cfg():
    try:
        with open(SETTINGS_FILE) as f:
            saved = json.load(f)
        cfg = dict(DEFAULT_CFG)
        # Scalar fields
        for k in ("opacity", "hover_opacity", "update_ms", "locked",
                  "always_on_top", "pos_x", "pos_y", "theme",
                  "skipped_version"):
            if k in saved:
                cfg[k] = saved[k]
        cfg["colors"] = saved.get("colors", {})

        # active_sensors — new field; derive from old "visible" if absent
        if "active_sensors" in saved:
            cfg["active_sensors"] = [
                k for k in saved["active_sensors"] if k in SENSOR_CATALOG
            ]
        else:
            old_vis = saved.get("visible", {})
            derived = [k for k in SENSOR_CATALOG if old_vis.get(k, False)]
            cfg["active_sensors"] = derived if derived else list(_DEFAULT_ACTIVE)

        # visible: only keys in active_sensors; default True if not saved
        saved_vis = saved.get("visible", {})
        cfg["visible"] = {
            k: saved_vis.get(k, True) for k in cfg["active_sensors"]
        }
        cfg = _sanitize_cfg(cfg)
        _log.info("Settings loaded from %s", SETTINGS_FILE)
        return cfg
    except FileNotFoundError:
        _log.info("No settings file found, using defaults.")
        return dict(DEFAULT_CFG)
    except json.JSONDecodeError as e:
        _log.warning("Settings file corrupted (%s), using defaults.", e)
        _backup_corrupt_settings()
        return dict(DEFAULT_CFG)
    except Exception as e:
        _log.error("Failed to load settings: %s", e)
        return dict(DEFAULT_CFG)


def _backup_corrupt_settings():
    """Rename corrupt settings file so it is not overwritten silently."""
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = SETTINGS_FILE + f".corrupt_{ts}"
    try:
        os.rename(SETTINGS_FILE, backup)
        _log.warning("Corrupt settings backed up to %s", backup)
    except Exception:
        pass


def save_cfg(cfg):
    """Atomically write cfg to SETTINGS_FILE (write-then-rename pattern)."""
    tmp = SETTINGS_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        # Atomic replace — avoids partial writes corrupting the file
        if os.path.exists(SETTINGS_FILE):
            os.replace(tmp, SETTINGS_FILE)
        else:
            os.rename(tmp, SETTINGS_FILE)
        _log.debug("Settings saved.")
    except Exception as e:
        _log.error("Failed to save settings: %s", e)
        try:
            os.remove(tmp)
        except Exception:
            pass


# ── Active sensor helpers ─────────────────────────────────────────────────────
def active_sensor_defs(cfg) -> list[SensorDef]:
    """Return ordered SensorDef list for sensors active in cfg."""
    return [SENSOR_CATALOG[k] for k in cfg["active_sensors"] if k in SENSOR_CATALOG]


# ── Colour helpers ────────────────────────────────────────────────────────────
def default_color(key: str) -> str:
    s = SENSOR_CATALOG.get(key)
    return s.color if s else "#e8e8e8"


def eff_color(cfg, key: str) -> str:
    """Return the active sensor colour: custom if set, else catalog default."""
    return cfg["colors"].get(key, default_color(key))
