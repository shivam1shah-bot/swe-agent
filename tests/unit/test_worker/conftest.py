"""
conftest.py for test_worker package.

Injects a tomllib shim so tests run on Python 3.9 (tomllib is stdlib only
from 3.11; tomli is already installed in the venv as a back-port).
"""
import sys

if "tomllib" not in sys.modules:
    import tomli  # noqa: F401
    sys.modules["tomllib"] = tomli  # type: ignore[assignment]
