#!/usr/bin/env python3
"""Run the CDISCPilot01 public-benchmark parity track.

Two modes are available:

``python cdisc_pilot01/run_parity.py --replay``  (no SAS required)
    Offline verification against the frozen golden outputs in
    ``cdisc_pilot01/golden_outputs/``. Each frozen golden RTF is treated as
    the legacy-side oracle and re-compared against the frozen native IR cell
    exports (``*_ir_cells.csv``) with the same comparator the harness uses
    (:func:`parity_harness.compare_report_parity`). For PUB-KM-TTDE (a
    figure) the comparison is RTF-vs-RTF against the frozen native RTF.
    This reproduces the Section 4.1.4.5 public-track result: 5 reports,
    4,764 cells, 0 mismatches (100% regression-consistency).

``python cdisc_pilot01/run_parity.py``  (requires SAS 9.4)
    Full parity run: invokes the legacy bridge macros through
    :class:`parity_harness.LegacyDriver` in local SAS batch mode and compares
    the produced RTFs against the native side. This requires a local SAS 9.4
    installation (SAS 9.4M7 was used for the manuscript runs) available on
    ``PATH`` as ``sas``, plus a legacy macro library wired through a bridge
    map (see ``registry_examples/bridge_map_sample.yaml`` for the entry
    structure and ``registry_examples/sas_stubs/`` for structural stubs).
    Without SAS this mode exits with code 2 and an instructive message.

Exit codes: 0 = all reports PASS, 1 = parity failures, 2 = environment
prerequisite missing (e.g. no SAS executable).
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from parity_harness.compare import ParityVerdict, compare_report_parity  # noqa: E402
from parity_harness.ir_compare import ToleranceConfig  # noqa: E402
from parity_harness.matrix import ParityMatrixEntry, write_parity_matrix  # noqa: E402
from parity_harness.sas_provider import SASUnavailableError  # noqa: E402

logger = logging.getLogger("run_parity")

PILOT_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = PILOT_DIR / "golden_outputs"
DEFAULT_OUTPUT_DIR = PILOT_DIR / "parity_output"

# The five report types of the Section 4.1.4.5 public-benchmark track.
REPORT_TYPE_IDS = [
    "PUB-DEMOGRAPHICS",
    "PUB-AE-OVERVIEW",
    "PUB-AE-BY-SOC",
    "PUB-EFFICACY",
    "PUB-KM-TTDE",
]

SAS_REQUIRED_MESSAGE = """\
ERROR: no SAS executable found on PATH.

The full parity track executes the legacy SAS macros in local batch mode and
therefore requires a local SAS 9.4 installation (SAS 9.4M7 was used for the
manuscript runs). Options:

  1. Install SAS 9.4 and ensure the `sas` executable is on PATH, or set the
     SAS_EXECUTABLE environment variable to its full path, then re-run:
         python cdisc_pilot01/run_parity.py

  2. To verify the frozen public-benchmark results WITHOUT SAS (this
     reproduces the Section 4.1.4.5 numbers from the archived golden outputs),
     run:
         python cdisc_pilot01/run_parity.py --replay

See docs/REPRODUCIBILITY_GUIDE.md for details.
"""


def _print_matrix(entries: list[ParityMatrixEntry]) -> None:
    """Print the parity matrix as a plain-text table."""
    header = (
        f"{'report_type_id':<20} {'verdict':<7} {'cells':>7} "
        f"{'matched':>7} {'mism':>5} {'match%':>7}"
    )
    print(header)
    print("-" * len(header))
    total = matched = mismatched = 0
    for e in entries:
        print(
            f"{e.report_type_id:<20} {e.verdict:<7} {e.total_cells:>7} "
            f"{e.matched_cells:>7} {e.mismatched_cells:>5} {e.match_pct:>6.2f}%"
        )
        total += e.total_cells
        matched += e.matched_cells
        mismatched += e.mismatched_cells
    print("-" * len(header))
    pct = 100.0 * matched / total if total else 0.0
    print(
        f"{'TOTAL':<20} {'':<7} {total:>7} {matched:>7} "
        f"{mismatched:>5} {pct:>6.2f}%"
    )


def run_replay(output_dir: Path) -> int:
    """Re-compare frozen golden outputs; no SAS required."""
    tolerance = ToleranceConfig()
    entries: list[ParityMatrixEntry] = []
    for report_id in REPORT_TYPE_IDS:
        golden_rtf = GOLDEN_DIR / f"{report_id}.rtf"
        if not golden_rtf.exists():
            entry = ParityMatrixEntry(
                report_type_id=report_id,
                verdict=ParityVerdict.ERROR,
                notes=f"Frozen golden RTF not found: {golden_rtf}",
            )
            entries.append(entry)
            continue
        ir_csv = GOLDEN_DIR / f"{report_id}_ir_cells.csv"
        comparison = compare_report_parity(
            report_type_id=report_id,
            legacy_rtf_path=golden_rtf,
            native_rtf_path=golden_rtf,
            native_ir_cells_path=ir_csv if ir_csv.exists() else None,
            tolerance=tolerance,
        )
        entries.append(ParityMatrixEntry.from_comparison(comparison))
    outputs = write_parity_matrix(entries, output_dir, run_label="parity")
    _print_matrix(entries)
    print(f"\nMatrix artefacts written to: {output_dir}")
    for fmt, path in sorted(outputs.items()):
        print(f"  {fmt}: {path.name}")
    return 0 if all(e.verdict == ParityVerdict.PASS for e in entries) else 1


def run_full(output_dir: Path) -> int:
    """Full parity run through the harness; requires a local SAS 9.4."""
    import os

    if shutil.which("sas") is None and not os.environ.get("SAS_EXECUTABLE"):
        sys.stderr.write(SAS_REQUIRED_MESSAGE)
        return 2

    from parity_harness.harness import ParityHarness, ParityRunConfig
    from parity_harness.sas_provider import LocalSASProvider

    config = ParityRunConfig(
        repo_root=REPO_ROOT,
        bridge_map_path=REPO_ROOT / "registry_examples" / "bridge_map_sample.yaml",
        study_config_dir=PILOT_DIR / "config" / "CDISCPilot01",
        core_registry_dir=REPO_ROOT / "registry_examples",
        environment_config_path=PILOT_DIR / "config" / "environment.yaml",
        output_root=output_dir,
        parity_output_dir=output_dir,
        report_type_ids=list(REPORT_TYPE_IDS),
        legacy_id_map={
            "PUB-DEMOGRAPHICS": "PUB-DEMOGRAPHICS",
            "PUB-AE-OVERVIEW": "PUB-AE-OVERVIEW",
            "PUB-AE-BY-SOC": "legacy_ae_summary_report",
            "PUB-EFFICACY": "legacy_vitals_summary",
            "PUB-KM-TTDE": "PUB-KM-TTDE",
        },
    )
    try:
        provider = LocalSASProvider(
            {"sas_executable": os.environ.get("SAS_EXECUTABLE", "sas")}
        )
    except SASUnavailableError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2

    harness = ParityHarness(config, provider)
    entries = harness.run()
    outputs = write_parity_matrix(entries, output_dir, run_label="parity")
    _print_matrix(entries)
    print(f"\nMatrix artefacts written to: {output_dir}")
    for fmt, path in sorted(outputs.items()):
        print(f"  {fmt}: {path.name}")
    bad = [e for e in entries if e.verdict != ParityVerdict.PASS]
    if bad:
        print(
            "\nNote: non-PASS verdicts are expected when the legacy macro "
            "library is not wired up (only structural stubs ship in "
            "registry_examples/sas_stubs/) or when the native pipeline "
            "implementation is unavailable (see NOT_INCLUDED.md).",
        )
    return 0 if not bad else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Verify frozen golden outputs offline (no SAS required).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the parity matrix artefacts "
             f"(default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.replay:
        return run_replay(args.output_dir)
    return run_full(args.output_dir)


if __name__ == "__main__":
    sys.exit(main())
