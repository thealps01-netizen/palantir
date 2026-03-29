"""tests/test_updater.py — Unit tests for updater.py (version comparison, network, integrity)."""

import hashlib
import os
import sys
import tempfile
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from updater import _parse, _is_newer, _find_installer_asset, _fetch_latest


# ── _parse ────────────────────────────────────────────────────────────────────

def test_parse_standard_tag():
    assert _parse("v1.2.3") == (1, 2, 3)

def test_parse_no_v_prefix():
    assert _parse("2.0.0") == (2, 0, 0)

def test_parse_single_digit():
    assert _parse("v1") == (1,)

def test_parse_four_parts():
    assert _parse("v1.2.3.4") == (1, 2, 3, 4)


# ── _is_newer ─────────────────────────────────────────────────────────────────

def test_is_newer_detects_major_bump():
    assert _is_newer("v2.0.0", current="1.0.0") is True

def test_is_newer_detects_minor_bump():
    assert _is_newer("v1.1.0", current="1.0.0") is True

def test_is_newer_detects_patch_bump():
    assert _is_newer("v1.0.1", current="1.0.0") is True

def test_is_newer_same_version_is_not_newer():
    assert _is_newer("v1.0.0", current="1.0.0") is False

def test_is_newer_older_tag_is_not_newer():
    assert _is_newer("v0.9.9", current="1.0.0") is False

def test_is_newer_uses_version_py_default():
    from version import __version__
    # Current version is never newer than itself
    assert _is_newer(f"v{__version__}") is False


# ── _find_installer_asset ─────────────────────────────────────────────────────

def test_find_installer_asset_finds_exe():
    release = {
        "assets": [
            {"name": "Palantir_Setup.exe", "browser_download_url": "https://example.com/setup.exe"},
            {"name": "source.zip",         "browser_download_url": "https://example.com/source.zip"},
        ]
    }
    assert _find_installer_asset(release) == "https://example.com/setup.exe"


def test_find_installer_asset_no_exe_returns_none():
    release = {
        "assets": [
            {"name": "source.tar.gz", "browser_download_url": "https://example.com/src.tar.gz"},
        ]
    }
    assert _find_installer_asset(release) is None


def test_find_installer_asset_empty_assets():
    assert _find_installer_asset({"assets": []}) is None


def test_find_installer_asset_missing_key():
    assert _find_installer_asset({}) is None


# ── _fetch_latest network error handling ──────────────────────────────────────

def test_fetch_latest_returns_none_on_url_error():
    """Network unavailable should return None, not raise."""
    with patch("updater.urllib.request.urlopen",
               side_effect=urllib.error.URLError("no network")):
        result = _fetch_latest("owner", "repo")
    assert result is None


def test_fetch_latest_returns_none_on_http_error():
    """HTTP 404 should return None, not raise."""
    with patch("updater.urllib.request.urlopen",
               side_effect=urllib.error.HTTPError(
                   url="", code=404, msg="Not Found", hdrs=None, fp=None)):
        result = _fetch_latest("owner", "repo")
    assert result is None


def test_fetch_latest_returns_none_on_timeout():
    """Timeout (subclass of URLError) should return None."""
    import socket
    with patch("updater.urllib.request.urlopen",
               side_effect=urllib.error.URLError(socket.timeout("timed out"))):
        result = _fetch_latest("owner", "repo")
    assert result is None


# ── SHA256 integrity check ─────────────────────────────────────────────────────

def test_sha256_mismatch_raises_value_error():
    """InstallerDownloader should raise ValueError when hash does not match."""
    import hashlib, tempfile, os
    from updater import InstallerDownloader

    # Write a dummy exe file
    tmp_dir = tempfile.mkdtemp()
    exe_path = os.path.join(tmp_dir, "Palantir_Setup.exe")
    with open(exe_path, "wb") as f:
        f.write(b"fake exe content")

    wrong_hash = "0" * 64  # clearly wrong SHA256

    # Simulate sidecar returning wrong hash
    sidecar_response = MagicMock()
    sidecar_response.__enter__ = lambda s: s
    sidecar_response.__exit__ = MagicMock(return_value=False)
    sidecar_response.read.return_value = wrong_hash.encode()

    with patch("updater.urllib.request.urlretrieve",
               side_effect=lambda url, dest, reporthook: open(dest, "wb").write(b"fake exe content")):
        with patch("updater.urllib.request.urlopen", return_value=sidecar_response):
            downloader = InstallerDownloader.__new__(InstallerDownloader)
            downloader._url = "https://example.com/Palantir_Setup.exe"

            errors = []
            downloader.error = MagicMock()
            downloader.error.emit = lambda msg: errors.append(msg)
            downloader.finished = MagicMock()
            downloader.progress = MagicMock()
            downloader._thread = MagicMock()

            downloader._run()

    assert len(errors) == 1
    assert "SHA256 mismatch" in errors[0] or "mismatch" in errors[0].lower()


def test_sha256_match_succeeds():
    """InstallerDownloader should emit finished when hash matches."""
    import tempfile, os
    from updater import InstallerDownloader

    content = b"valid exe content"
    correct_hash = hashlib.sha256(content).hexdigest()

    sidecar_response = MagicMock()
    sidecar_response.__enter__ = lambda s: s
    sidecar_response.__exit__ = MagicMock(return_value=False)
    sidecar_response.read.return_value = correct_hash.encode()

    finished_paths = []

    def fake_urlretrieve(url, dest, reporthook=None):
        with open(dest, "wb") as f:
            f.write(content)

    with patch("updater.urllib.request.urlretrieve", side_effect=fake_urlretrieve):
        with patch("updater.urllib.request.urlopen", return_value=sidecar_response):
            downloader = InstallerDownloader.__new__(InstallerDownloader)
            downloader._url = "https://example.com/Palantir_Setup.exe"
            downloader.error = MagicMock()
            downloader.finished = MagicMock()
            downloader.finished.emit = lambda p: finished_paths.append(p)
            downloader.progress = MagicMock()
            downloader.progress.emit = MagicMock()
            downloader._thread = MagicMock()

            downloader._run()

    assert len(finished_paths) == 1
    assert finished_paths[0].endswith(".exe")


def test_sha256_no_sidecar_continues():
    """When .sha256 sidecar is missing, download should still complete (with warning)."""
    import tempfile
    from updater import InstallerDownloader

    content = b"exe without sidecar"
    finished_paths = []

    def fake_urlretrieve(url, dest, reporthook=None):
        with open(dest, "wb") as f:
            f.write(content)

    with patch("updater.urllib.request.urlretrieve", side_effect=fake_urlretrieve):
        with patch("updater.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("no sidecar")):
            downloader = InstallerDownloader.__new__(InstallerDownloader)
            downloader._url = "https://example.com/Palantir_Setup.exe"
            downloader.error = MagicMock()
            downloader.finished = MagicMock()
            downloader.finished.emit = lambda p: finished_paths.append(p)
            downloader.progress = MagicMock()
            downloader.progress.emit = MagicMock()
            downloader._thread = MagicMock()

            downloader._run()

    # Should still finish (sidecar absence is not fatal)
    assert len(finished_paths) == 1
