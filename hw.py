"""hw.py — Hardware data sources: MSI Afterburner shared memory + Windows RAM.

Also provides HardwareWorker — a QThread-based poller that emits sensor data
on a configurable interval without blocking the UI thread.
"""

import ctypes, math
from logger import get_logger

_log = get_logger("hw")

# ── MSI Afterburner shared memory (MAHM v2.0) ─────────────────────────────────
FILE_MAP_READ = 0x0004
MAX_PATH      = 260
MAHM_SIG      = 0x4D41484D


class _Hdr(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("sig",          ctypes.c_uint32),
        ("ver",          ctypes.c_uint32),
        ("headerSize",   ctypes.c_uint32),
        ("num",          ctypes.c_uint32),
        ("entrySize",    ctypes.c_uint32),
        ("time",         ctypes.c_uint32),
        ("numGpu",       ctypes.c_uint32),
        ("gpuEntrySize", ctypes.c_uint32),
    ]


class _Entry(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("srcName",  ctypes.c_char * MAX_PATH),
        ("srcUnits", ctypes.c_char * MAX_PATH),
        ("locName",  ctypes.c_char * MAX_PATH),
        ("locUnits", ctypes.c_char * MAX_PATH),
        ("locDesc",  ctypes.c_char * MAX_PATH),
        ("data",     ctypes.c_float),
        ("minVal",   ctypes.c_float),
        ("maxVal",   ctypes.c_float),
        ("fmt",      ctypes.c_uint32),
        ("flags",    ctypes.c_uint32),
        ("locId",    ctypes.c_uint32),
    ]


# ── Pre-computed sizes, reusable buffers, kernel32 setup (once at import) ─────
_HDR_SIZE   = ctypes.sizeof(_Hdr)
_ENTRY_SIZE = ctypes.sizeof(_Entry)
_hdr_buf    = (ctypes.c_byte * _HDR_SIZE)()
_entry_buf  = (ctypes.c_byte * _ENTRY_SIZE)()

_mahm_sensor_count: int = 0   # tracks last reported count to avoid log spam

_k32 = ctypes.windll.kernel32
_k32.OpenFileMappingW.restype  = ctypes.c_void_p
_k32.MapViewOfFile.restype     = ctypes.c_void_p
_k32.UnmapViewOfFile.argtypes  = [ctypes.c_void_p]
_k32.CloseHandle.argtypes      = [ctypes.c_void_p]


def read_mahm() -> dict:
    hm = _k32.OpenFileMappingW(FILE_MAP_READ, False, "MAHMSharedMemory")
    if not hm:
        return {}
    pv = _k32.MapViewOfFile(hm, FILE_MAP_READ, 0, 0, 0)
    if not pv:
        _k32.CloseHandle(hm)
        return {}
    try:
        ctypes.memmove(_hdr_buf, pv, _HDR_SIZE)
        hdr = _Hdr.from_buffer(_hdr_buf)
        if hdr.sig != MAHM_SIG:
            _log.debug("MAHM signature mismatch — Afterburner not running?")
            return {}
        num    = hdr.num
        hdr_sz = hdr.headerSize or _HDR_SIZE
        sz     = hdr.entrySize  or _ENTRY_SIZE
        if num > 512 or sz < 100 or sz > 8192:
            _log.warning("MAHM header sanity check failed (num=%d, sz=%d)", num, sz)
            return {}
        out = {}
        for i in range(num):
            try:
                ctypes.memmove(_entry_buf, pv + hdr_sz + i * sz, _ENTRY_SIZE)
                e = _Entry.from_buffer(_entry_buf)
                n = e.srcName.decode("utf-8", errors="ignore").rstrip("\x00").lower()
                if n:
                    v   = e.data
                    mxv = e.maxVal
                    if math.isfinite(v) and v < 3.4e38:
                        mx = mxv if (math.isfinite(mxv) and 0 < mxv < 3.4e38) else v
                        out[n] = (v, mx)
            except Exception:
                break
        if out:
            global _mahm_sensor_count
            if len(out) != _mahm_sensor_count:
                _mahm_sensor_count = len(out)
                _log.info("MAHM connected — %d sensors available", len(out))
        return out
    except Exception as e:
        _log.error("MAHM read error: %s", e)
        return {}
    finally:
        _k32.UnmapViewOfFile(pv)
        _k32.CloseHandle(hm)


def list_mahm_sensors() -> dict[str, float]:
    """Return all available MAHM sensor names → current values.

    Used by the Settings dialog dropdown to show what Afterburner is exposing.
    Returns empty dict if Afterburner is not running.
    """
    return {k: v for k, (v, _mx) in read_mahm().items()}


# ── Windows RAM (GlobalMemoryStatusEx) ────────────────────────────────────────
class _MemStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength",                ctypes.c_ulong),
        ("dwMemoryLoad",            ctypes.c_ulong),
        ("ullTotalPhys",            ctypes.c_ulonglong),
        ("ullAvailPhys",            ctypes.c_ulonglong),
        ("ullTotalPageFile",        ctypes.c_ulonglong),
        ("ullAvailPageFile",        ctypes.c_ulonglong),
        ("ullTotalVirtual",         ctypes.c_ulonglong),
        ("ullAvailVirtual",         ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_ram_pct() -> float:
    ms = _MemStatus()
    ms.dwLength = ctypes.sizeof(_MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    return float(ms.dwMemoryLoad)


# ── Windows API fallback dispatch ─────────────────────────────────────────────
_WIN_FALLBACKS = {
    "ram_usage": get_ram_pct,
}


# ── Sensor pick helpers ───────────────────────────────────────────────────────
def _pick_sensor(raw: dict, candidates: tuple) -> tuple[float | None, float | None]:
    """Return (current_val, session_max) for the first matching candidate."""
    for c in candidates:
        for k, tup in raw.items():
            if c in k:
                return tup   # (val, max_val)
    return (None, None)


def get_data(sensors: list) -> tuple[dict, dict, str]:
    """Return ({key: val}, {key: session_max}, source_label).

    sensors: list of SensorDef (from cfg.active_sensor_defs(cfg))
    session_max is MAHM's maxVal for MAHM sensors; bar_max for Windows API sensors.
    """
    raw = read_mahm()
    vals: dict  = {}
    maxes: dict = {}
    for s in sensors:
        if s.mahm_names:
            v, mx = _pick_sensor(raw, s.mahm_names)
            vals[s.key]  = v
            maxes[s.key] = mx
        else:
            fn = _WIN_FALLBACKS.get(s.key)
            if fn:
                try:
                    vals[s.key] = fn()
                except Exception:
                    vals[s.key] = None
            else:
                vals[s.key] = None
            maxes[s.key] = s.bar_max   # Windows API sensors use fixed bar_max
    return vals, maxes, ("MSI Afterburner" if raw else "N/A")


# ── QThread-based async hardware worker ───────────────────────────────────────
# Import PyQt6 lazily so hw.py can still be used without Qt (e.g. in unit tests)
try:
    from PyQt6.QtCore import QThread, pyqtSignal, QObject

    class HardwareWorker(QObject):
        """Polls hardware data on a background QThread.

        Usage:
            worker = HardwareWorker(sensors, interval_ms=1000)
            thread = QThread()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.data_ready.connect(my_slot)
            thread.start()
            # to stop:
            worker.stop()
            thread.quit()
        """

        data_ready = pyqtSignal(dict, dict, str)   # (vals, maxes, source_label)

        def __init__(self, sensors: list, interval_ms: int = 1000):
            super().__init__()
            self._sensors     = sensors
            self._interval_ms = interval_ms
            self._running     = False

        def set_sensors(self, sensors: list) -> None:
            self._sensors = sensors

        def set_interval(self, interval_ms: int) -> None:
            self._interval_ms = interval_ms

        def run(self) -> None:
            self._running = True
            _log.debug("HardwareWorker started (interval=%dms)", self._interval_ms)
            while self._running:
                try:
                    vals, maxes, src = get_data(self._sensors)
                    self.data_ready.emit(vals, maxes, src)
                except Exception as e:
                    _log.error("HardwareWorker poll error: %s", e)
                QThread.msleep(self._interval_ms)
            _log.debug("HardwareWorker stopped.")

        def stop(self) -> None:
            self._running = False

except ImportError:
    # PyQt6 not available — HardwareWorker simply won't exist
    pass
