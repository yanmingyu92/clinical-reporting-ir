"""Emit the parity matrix as JSON, CSV, and simple HTML.

The matrix is the single artefact reviewers consult to see which report
types have achieved parity and which still diverge. Each row of the matrix
corresponds to one ``report_type_id``.
"""

from __future__ import annotations

import csv
import html
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .compare import ParityComparison, ParityVerdict

logger = logging.getLogger(__name__)


@dataclass
class ParityMatrixEntry:
    """One row of the parity matrix."""

    report_type_id: str
    verdict: str
    total_cells: int = 0
    matched_cells: int = 0
    mismatched_cells: int = 0
    match_pct: float = 0.0
    shape_mismatch: bool = False
    legacy_rtf: str = ""
    native_rtf: str = ""
    native_ir_cells: str = ""
    notes: str = ""
    top_diffs: list[dict] = field(default_factory=list)

    @classmethod
    def from_comparison(cls, cmp: ParityComparison, max_diffs: int = 10) -> "ParityMatrixEntry":
        return cls(
            report_type_id=cmp.report_type_id,
            verdict=cmp.verdict,
            total_cells=cmp.total_cells,
            matched_cells=cmp.matched_cells,
            mismatched_cells=cmp.mismatched_cells,
            match_pct=cmp.match_pct,
            shape_mismatch=cmp.shape_mismatch,
            legacy_rtf=cmp.legacy_rtf,
            native_rtf=cmp.native_rtf,
            native_ir_cells=cmp.native_ir_cells,
            notes=cmp.notes,
            top_diffs=[asdict(d) for d in cmp.diffs[:max_diffs]],
        )


def _summary_counts(entries: list[ParityMatrixEntry]) -> dict[str, int]:
    counts = {v: 0 for v in (
        ParityVerdict.PASS,
        ParityVerdict.FAIL,
        ParityVerdict.ERROR,
        ParityVerdict.SKIP,
    )}
    for entry in entries:
        counts[entry.verdict] = counts.get(entry.verdict, 0) + 1
    return counts


def write_parity_matrix(
    entries: list[ParityMatrixEntry],
    output_dir: Path,
    run_label: str = "parity",
) -> dict[str, Path]:
    """Write the matrix in JSON, CSV, and HTML formats."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _summary_counts(entries)
    generated_at = datetime.now(timezone.utc).isoformat()

    json_path = output_dir / f"{run_label}_matrix.json"
    payload = {
        "generated_at": generated_at,
        "summary": summary,
        "total_report_types": len(entries),
        "entries": [asdict(e) for e in entries],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    csv_path = output_dir / f"{run_label}_matrix.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "report_type_id", "verdict", "total_cells", "matched_cells",
            "mismatched_cells", "match_pct", "shape_mismatch", "notes",
        ])
        for entry in entries:
            writer.writerow([
                entry.report_type_id, entry.verdict, entry.total_cells,
                entry.matched_cells, entry.mismatched_cells,
                f"{entry.match_pct:.2f}",
                "yes" if entry.shape_mismatch else "no",
                entry.notes,
            ])

    html_path = output_dir / f"{run_label}_matrix.html"
    html_path.write_text(_render_html(entries, summary, generated_at), encoding="utf-8")

    logger.info(
        "Parity matrix written: %s (PASS=%d FAIL=%d ERROR=%d SKIP=%d)",
        json_path, summary.get(ParityVerdict.PASS, 0),
        summary.get(ParityVerdict.FAIL, 0),
        summary.get(ParityVerdict.ERROR, 0),
        summary.get(ParityVerdict.SKIP, 0),
    )
    return {"json": json_path, "csv": csv_path, "html": html_path}


def _render_html(
    entries: list[ParityMatrixEntry],
    summary: dict[str, int],
    generated_at: str,
) -> str:
    row_html_parts: list[str] = []
    for entry in entries:
        row_html_parts.append(
            "<tr class='{verdict}'>"
            "<td>{rid}</td><td>{verdict}</td>"
            "<td>{total}</td><td>{matched}</td><td>{mism}</td>"
            "<td>{pct:.2f}</td><td>{shape}</td><td>{notes}</td>"
            "</tr>".format(
                verdict=html.escape(entry.verdict.lower()),
                rid=html.escape(entry.report_type_id),
                total=entry.total_cells,
                matched=entry.matched_cells,
                mism=entry.mismatched_cells,
                pct=entry.match_pct,
                shape="yes" if entry.shape_mismatch else "no",
                notes=html.escape(entry.notes),
            )
        )
    rows_html = "\n".join(row_html_parts)
    summary_html = " | ".join(f"{k}: {v}" for k, v in sorted(summary.items()))
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Framework Parity Matrix</title>"
        "<style>body{font-family:Arial,sans-serif;margin:1em;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #aaa;padding:4px 8px;font-size:12px;}"
        "tr.pass{background:#e6f4ea;}tr.fail{background:#fce8e6;}"
        "tr.error{background:#fff4e5;}tr.skip{background:#f1f3f4;}"
        "</style></head><body>"
        f"<h1>Framework Parity Matrix</h1>"
        f"<p>Generated: {html.escape(generated_at)}</p>"
        f"<p>Summary: {html.escape(summary_html)}</p>"
        "<table><thead><tr><th>Report Type</th><th>Verdict</th>"
        "<th>Cells</th><th>Match</th><th>Diff</th><th>Match %</th>"
        "<th>Shape</th><th>Notes</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table></body></html>"
    )
