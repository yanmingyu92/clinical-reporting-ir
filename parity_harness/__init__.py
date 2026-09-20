"""Parity harness for the modernized framework vs the legacy macro library.

This package compares the output of the modernized-framework native pipeline
against the legacy SAS macro library (invoked via the legacy bridge). It is
intended as
the regression gate used during phased migration: every report type that has
both a native implementation and a legacy bridge must demonstrate identical
results before the legacy bridge is retired.

Public API:
    :class:`ParityHarness`         - Top-level orchestrator.
    :func:`run_parity_suite`       - Convenience entry-point.
    :class:`LegacyDriver`          - Invokes the legacy bridge macro via SAS.
    :class:`NativeDriver`          - Invokes the modernized-framework pipeline.
    :func:`compare_report_parity`  - Cell-level tolerant comparison.
    :func:`write_parity_matrix`    - Emits JSON / CSV / HTML pass-fail matrix.
"""

from __future__ import annotations

from .compare import (
    ParityComparison,
    ParityVerdict,
    compare_report_parity,
)
from .harness import ParityHarness, run_parity_suite
from .legacy_driver import LegacyDriver, LegacyRun
from .matrix import ParityMatrixEntry, write_parity_matrix
from .native_driver import NativeDriver, NativeRun
from .rtf_extract import RtfTable, extract_tables_from_rtf

__all__ = [
    "LegacyDriver",
    "LegacyRun",
    "NativeDriver",
    "NativeRun",
    "ParityComparison",
    "ParityHarness",
    "ParityMatrixEntry",
    "ParityVerdict",
    "RtfTable",
    "compare_report_parity",
    "extract_tables_from_rtf",
    "run_parity_suite",
    "write_parity_matrix",
]
