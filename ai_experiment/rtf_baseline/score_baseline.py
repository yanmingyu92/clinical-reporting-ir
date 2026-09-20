#!/usr/bin/env python3
"""Recompute the Table 11 (Section 4.2.6) scores from the shipped artifacts.

Stdlib-only. Run from the repository root:

    python ai_experiment/rtf_baseline/score_baseline.py

Reproduces: Task 1 numeric-extraction recall IR 50/55 (90.9%) vs
RTF 27/55 (49.1%); prints the matched/missing ground-truth values per
condition. Task 2 concept recall (5/5 vs 4/5) was scored by hand against
the pre-registered five-concept set; see SCORING.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
IR_SAMPLE = HERE.parent / "inputs" / "ir_demographics_sample.json"

NUM_RE = re.compile(r"-?\d+\.?\d*")
TOL = 0.05


def ground_truth_values(ir_json_path: Path) -> set[float]:
    """Distinct numeric tokens across cell_value and cell_formatted.

    This is the exact ground-truth derivation used for Table 11: every
    numeric token appearing in either the raw numeric field or the display
    string (e.g. "53 (61.6%)" contributes both 53 and 61.6), deduplicated.
    """
    vals: set[float] = set()
    for cell in json.loads(ir_json_path.read_text(encoding="utf-8")):
        for fld in ("cell_value", "cell_formatted"):
            v = cell.get(fld)
            if v is None:
                continue
            for m in NUM_RE.finditer(str(v)):
                vals.add(round(float(m.group()), 4))
    return vals


def numeric_recall(response: str, truth: set[float]) -> set[float]:
    rep: set[float] = set()
    for m in NUM_RE.finditer(response):
        try:
            rep.add(round(float(m.group()), 4))
        except ValueError:
            pass
    return {t for t in truth if any(abs(t - r) <= TOL for r in rep)}


def main() -> None:
    truth = ground_truth_values(IR_SAMPLE)
    print(f"Ground-truth numeric values: {len(truth)}")
    for cond in ("ir", "rtf"):
        resp = (HERE / "responses" / f"task1_{cond}_response.txt").read_text(
            encoding="utf-8"
        )
        found = numeric_recall(resp, truth)
        pct = 100.0 * len(found) / len(truth)
        print(
            f"Task 1 {cond.upper():>3} condition: {len(found)}/{len(truth)} "
            f"= {pct:.1f}%  (missing: {sorted(truth - found)})"
        )


if __name__ == "__main__":
    main()
