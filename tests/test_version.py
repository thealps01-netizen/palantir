"""tests/test_version.py — Sanity checks for version.py consistency."""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from version import __version__, __version_tuple__, APP_NAME


def test_version_is_valid_semver():
    assert re.fullmatch(r'\d+\.\d+\.\d+', __version__), \
        f"__version__ gecerli semver degil: {__version__!r}"


def test_version_tuple_matches_string():
    expected = tuple(int(x) for x in __version__.split('.'))
    assert __version_tuple__ == expected, \
        f"__version_tuple__ {__version_tuple__} != string'den turetilen {expected}"


def test_app_name_is_set():
    assert APP_NAME and isinstance(APP_NAME, str)
