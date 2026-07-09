"""Optional project config for custom claim / evidence / hedge patterns.

Looks for (in order):

1. An explicit path passed by the caller.
2. ``.neo-evidence-gate.toml`` walking up from the start directory.
3. A ``[tool.neo-evidence-gate]`` table in ``pyproject.toml``.

Uses stdlib ``tomllib`` on Python 3.11+. On 3.9/3.10 it tries optional
``tomli`` if installed; otherwise config loading is a no-op (defaults only)
so the package keeps zero *required* runtime dependencies.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover - exercised on 3.9/3.10
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


# A claim entry is (name, pattern_string).
ClaimEntry = Tuple[str, str]


@dataclass
class GateConfig:
    """Merged pattern overrides loaded from a project config file."""

    claims_add: List[ClaimEntry] = field(default_factory=list)
    claims_replace: bool = False
    evidence_add: List[str] = field(default_factory=list)
    evidence_replace: bool = False
    hedges_add: List[str] = field(default_factory=list)
    hedges_replace: bool = False
    source: Optional[str] = None  # path that was loaded, for diagnostics

    @property
    def empty(self) -> bool:
        return not (
            self.claims_add
            or self.claims_replace
            or self.evidence_add
            or self.evidence_replace
            or self.hedges_add
            or self.hedges_replace
        )


def _parse_claim_entries(raw: Any) -> List[ClaimEntry]:
    """Normalize claim entries from TOML into ``(name, pattern)`` pairs.

    Accepts:
    - ``[["name", "pattern"], ...]``
    - ``[{name = "...", pattern = "..."}, ...]``
    - ``["pattern", ...]``  (name derived as ``custom_N``)
    """
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError("claims_add must be a list")
    out: List[ClaimEntry] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            name = str(item.get("name") or f"custom_{i}")
            pat = item.get("pattern")
            if not pat:
                raise ValueError(f"claim entry {i} missing 'pattern'")
            out.append((name, str(pat)))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            out.append((str(item[0]), str(item[1])))
        elif isinstance(item, str):
            out.append((f"custom_{i}", item))
        else:
            raise ValueError(
                f"claim entry {i} must be [name, pattern], "
                "{name, pattern}, or a pattern string"
            )
    return out


def _parse_string_list(raw: Any, field_name: str) -> List[str]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a list of strings")
    out: List[str] = []
    for i, item in enumerate(raw):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{i}] must be a string")
        out.append(item)
    return out


def _table_to_config(table: Dict[str, Any], source: str) -> GateConfig:
    """Build a :class:`GateConfig` from a TOML table dict."""
    # Prefer claims_add; also accept bare "claims" as additive unless replace.
    claims_raw = table.get("claims_add", table.get("claims", []))
    evidence_raw = table.get("evidence_add", table.get("evidence", []))
    hedges_raw = table.get("hedges_add", table.get("hedges", []))

    return GateConfig(
        claims_add=_parse_claim_entries(claims_raw),
        claims_replace=bool(table.get("claims_replace", False)),
        evidence_add=_parse_string_list(evidence_raw, "evidence_add"),
        evidence_replace=bool(table.get("evidence_replace", False)),
        hedges_add=_parse_string_list(hedges_raw, "hedges_add"),
        hedges_replace=bool(table.get("hedges_replace", False)),
        source=source,
    )


def _load_toml(path: Path) -> Dict[str, Any]:
    if tomllib is None:
        raise RuntimeError(
            "TOML config requires Python 3.11+ (tomllib) or the optional "
            "'tomli' package on Python 3.9/3.10"
        )
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _config_from_file(path: Path) -> Optional[GateConfig]:
    data = _load_toml(path)
    if path.name == "pyproject.toml":
        tool = data.get("tool") or {}
        table = tool.get("neo-evidence-gate")
        if not table:
            return None
        return _table_to_config(table, str(path))
    # Dedicated config file: top-level keys, or optional nested table.
    if "tool" in data and isinstance(data["tool"], dict):
        nested = data["tool"].get("neo-evidence-gate")
        if isinstance(nested, dict):
            return _table_to_config(nested, str(path))
    return _table_to_config(data, str(path))


def discover_config_path(start: Optional[Path] = None) -> Optional[Path]:
    """Walk parents looking for a project config file."""
    cur = (start or Path.cwd()).resolve()
    if cur.is_file():
        cur = cur.parent
    for directory in [cur, *cur.parents]:
        dedicated = directory / ".neo-evidence-gate.toml"
        if dedicated.is_file():
            return dedicated
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            # Only treat it as a hit if the table exists (cheap text check first).
            try:
                text = pyproject.read_text(encoding="utf-8")
            except OSError:
                continue
            if "[tool.neo-evidence-gate]" in text:
                return pyproject
        # Stop at filesystem root; parents eventually repeats root on some OS.
        if directory.parent == directory:
            break
    return None


def load_config(
    path: Optional[str] = None,
    *,
    start: Optional[Path] = None,
    required: bool = False,
) -> GateConfig:
    """Load project config.

    Parameters
    ----------
    path:
        Explicit config file path. If omitted, discover from ``start`` / cwd.
    start:
        Directory to begin discovery from.
    required:
        If True, raise when the path is missing or unreadable. Discovery
        misses still return an empty config unless ``path`` was given.
    """
    if path:
        p = Path(path)
        if not p.is_file():
            if required:
                raise FileNotFoundError(f"config not found: {path}")
            return GateConfig()
        try:
            cfg = _config_from_file(p)
            return cfg or GateConfig(source=str(p))
        except Exception:
            if required:
                raise
            raise

    found = discover_config_path(start)
    if not found:
        return GateConfig()

    # Without a TOML parser on 3.9/3.10, fail soft (defaults only).
    if tomllib is None:
        if required:
            raise RuntimeError(
                "TOML config requires Python 3.11+ or optional 'tomli'"
            )
        return GateConfig()

    cfg = _config_from_file(found)
    return cfg or GateConfig(source=str(found))


def toml_available() -> bool:
    """Return True when a TOML parser is importable."""
    return tomllib is not None


# Re-export for type checkers / tests.
__all__ = [
    "GateConfig",
    "load_config",
    "discover_config_path",
    "toml_available",
]
