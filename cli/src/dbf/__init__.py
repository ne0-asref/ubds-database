"""dbf — Universal Board Description Standard CLI."""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("dbf")
except PackageNotFoundError:  # pragma: no cover - editable/source fallback
    __version__ = "0.1.0"
