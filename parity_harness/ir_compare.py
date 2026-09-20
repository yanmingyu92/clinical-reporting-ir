"""Tolerance configuration and cell-value comparison primitives.

Vendored, self-contained subset of the framework's IR comparison utility.
Only the pieces the parity harness needs are included: the
:class:`ToleranceConfig` settings object and the numeric/string cell-value
matchers used by :mod:`parity_harness.compare`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ToleranceConfig:
    """Tolerance settings for numeric comparison."""

    absolute: float = 1e-10
    relative: float = 1e-8
    mode: str = "either"  # "either" | "both" | "absolute" | "relative"


def _is_numeric_type(cell_type: str) -> bool:
    """Check if a cell type is numeric."""
    return cell_type.lower() in ("integer", "decimal", "pvalue", "percentage")


def _values_match_numeric(
    primary_raw: Optional[str],
    qc_raw: Optional[str],
    tolerance: ToleranceConfig,
) -> tuple[bool, Optional[float]]:
    """Compare two numeric values with tolerance. Returns (matched, difference)."""
    if primary_raw is None and qc_raw is None:
        return True, None
    if primary_raw is None or qc_raw is None:
        return False, None

    try:
        p_val = float(primary_raw)
        q_val = float(qc_raw)
    except (ValueError, TypeError):
        return primary_raw == qc_raw, None

    diff = abs(p_val - q_val)

    if tolerance.mode == "absolute":
        return diff <= tolerance.absolute, diff
    elif tolerance.mode == "relative":
        denom = max(abs(p_val), abs(q_val), 1e-30)
        return (diff / denom) <= tolerance.relative, diff
    else:  # "either" (default)
        abs_ok = diff <= tolerance.absolute
        denom = max(abs(p_val), abs(q_val), 1e-30)
        rel_ok = (diff / denom) <= tolerance.relative
        if tolerance.mode == "both":
            return abs_ok and rel_ok, diff
        return abs_ok or rel_ok, diff


def _values_match_string(primary_fmt: str, qc_fmt: str) -> bool:
    """Compare two string values after normalization."""
    p_norm = " ".join(primary_fmt.split()).lower()
    q_norm = " ".join(qc_fmt.split()).lower()
    return p_norm == q_norm
