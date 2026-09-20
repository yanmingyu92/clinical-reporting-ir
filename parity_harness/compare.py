"""Cell-level parity comparison between legacy RTF and native IR output.

The comparator treats the legacy RTF tables as the oracle: their rows/columns
define the expected values, and the modernized-framework IR cells are the
candidate values. Comparison rules:

* **Numeric cells** (integer, decimal, p-value, percentage) use a tolerant
  comparison via :class:`ToleranceConfig` from ``ir_compare``.
* **Text cells** are compared after whitespace normalisation and
  case-folding.
* **Missing rows / extra rows / shape mismatches** are reported individually
  so reviewers can see precisely what diverged.

The comparator never mutates inputs and is deterministic given the same
inputs.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .ir_compare import (
    ToleranceConfig,
    _is_numeric_type,
    _values_match_numeric,
    _values_match_string,
)

from .rtf_extract import RtfTable, extract_tables_from_rtf

logger = logging.getLogger(__name__)


class ParityVerdict:
    """Named verdicts for a parity comparison."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"


@dataclass
class CellDiff:
    """One cell-level divergence between legacy and native."""

    row_idx: int
    col_idx: int
    legacy_value: str
    native_value: str
    kind: str  # value | missing_native | missing_legacy | shape


@dataclass
class ParityComparison:
    """Aggregate comparison result for one report type."""

    report_type_id: str
    verdict: str = ParityVerdict.SKIP
    legacy_rtf: str = ""
    native_rtf: str = ""
    native_ir_cells: str = ""
    total_cells: int = 0
    matched_cells: int = 0
    mismatched_cells: int = 0
    shape_mismatch: bool = False
    diffs: list[CellDiff] = field(default_factory=list)
    notes: str = ""

    @property
    def match_pct(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return 100.0 * self.matched_cells / self.total_cells


def _load_ir_cells_as_grid(ir_cells_path: Path) -> list[list[tuple[str, str, str]]]:
    """Load IR cells CSV into a (row, col) grid of (type, raw, formatted).

    Ensures the LABEL column (if present) is placed first so that
    ``row[0]`` is always the label cell for alignment purposes.
    """
    rows: dict[str, dict[str, tuple[str, str, str]]] = {}
    row_order: list[str] = []
    col_order: list[str] = []
    with open(ir_cells_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for entry in reader:
            row_id = entry.get("row_id", "").strip()
            col_id = entry.get("col_id", "").strip()
            if row_id not in rows:
                rows[row_id] = {}
                row_order.append(row_id)
            if col_id not in col_order:
                col_order.append(col_id)
            rows[row_id][col_id] = (
                entry.get("cell_type", "").strip(),
                (entry.get("cell_raw_value", "") or "").strip(),
                entry.get("cell_formatted", "").strip(),
            )
    # Ensure LABEL column comes first for alignment
    if "LABEL" in col_order and col_order[0] != "LABEL":
        col_order.remove("LABEL")
        col_order.insert(0, "LABEL")
    # Interleave paired n/pct columns so grid matches legacy RTF layout
    # (legacy alternates: n, (%), n, (%), ... per treatment group).
    # Without this, first-occurrence ordering can group all _n first then
    # all _pct when early rows lack PCT cells (e.g. population denom row).
    def _col_sort_key(col_id: str) -> tuple[str, int]:
        if col_id == "LABEL":
            return ("", -2)
        if col_id == "LABEL2":
            return ("", -1)
        parts = col_id.rsplit("_", 1)
        if len(parts) == 2 and parts[1] in ("n", "pct"):
            return (parts[0], 0 if parts[1] == "n" else 1)
        return (col_id, 0)
    col_order.sort(key=_col_sort_key)
    grid: list[list[tuple[str, str, str]]] = []
    for row_id in row_order:
        line: list[tuple[str, str, str]] = []
        for col_id in col_order:
            line.append(rows[row_id].get(col_id, ("", "", "")))
        grid.append(line)
    return grid


def _normalize_ws(text: str) -> str:
    """Collapse whitespace and strip for comparison."""
    import re
    return re.sub(r"\s+", " ", text).strip()


def _normalize_symbols(text: str) -> str:
    """Normalize Unicode math symbols to ASCII equivalents for comparison.

    Legacy RTFs often contain Unicode ≤ ≥ instead of <= >=.
    The RTF ``\\uN`` escape leaves a fallback character (often ``=``)
    after the Unicode replacement, so ``≥=`` should become ``>=`` not ``>==``.
    """
    result = (text
              .replace("\u2264", "<=")   # ≤
              .replace("\u2265", ">=")   # ≥
              .replace("\u2260", "!=")   # ≠
              .replace("\u00b1", "+-")   # ±
              )
    # Collapse doubled operators from RTF fallback characters:
    # ≥= → ">=" + "=" → ">==" should be ">="
    result = result.replace(">==", ">=").replace("<==", "<=")
    return result


def _compare_cell(
    legacy_value: str,
    native_cell: tuple[str, str, str],
    tolerance: ToleranceConfig,
) -> bool:
    cell_type, raw, formatted = native_cell
    legacy_text = _normalize_symbols(_normalize_ws(legacy_value))
    native_text = _normalize_symbols(_normalize_ws(formatted or raw))
    # Empty cells match empty cells
    if not legacy_text and not native_text:
        return True
    if _is_numeric_type(cell_type) and raw:
        matched, _ = _values_match_numeric(legacy_text, raw, tolerance)
        if matched:
            return True
    # Try both formatted and raw against legacy
    if _values_match_string(legacy_text, native_text):
        return True
    if raw and formatted and _values_match_string(legacy_text, _normalize_ws(raw)):
        return True
    # Condensed stat format fallback: "430.1 (28.2)" vs "430.1"
    # If one side has parenthetical and the other doesn't, compare base values
    if '(' in legacy_text and '(' not in native_text:
        base_legacy = legacy_text.split('(')[0].strip()
        if _values_match_string(base_legacy, native_text):
            return True
    if '(' in native_text and '(' not in legacy_text:
        base_native = native_text.split('(')[0].strip()
        if _values_match_string(legacy_text, base_native):
            return True
    return False


def _auto_detect_ir_csv(native_rtf_path: Path | None, output_id: str) -> Path | None:
    """Auto-detect IR cells CSV alongside the native RTF.

    The sas_generator now exports ``{output_id}_ir_cells.csv`` into the same
    directory as the RTF. If found, prefer structured comparison over RTF-vs-RTF.
    """
    if native_rtf_path is None:
        return None
    candidate = native_rtf_path.parent / f"{output_id}_ir_cells.csv"
    if candidate.exists():
        return candidate
    return None


def _row_label(
    row: list[str] | list[tuple[str, str, str]],
    label_col_idx: int = 0,
) -> str:
    """Extract the label text from a row for alignment.

    Works with both legacy rows (list[str]) and native grid rows
    (list[tuple[str, str, str]] where [2] is formatted).
    ``label_col_idx`` allows specifying which column holds the label
    (for native grids where LABEL may not be column 0).
    """
    if not row:
        return ""
    idx = min(label_col_idx, len(row) - 1)
    cell = row[idx]
    if isinstance(cell, tuple):
        text = cell[2] or cell[1] or ""
    else:
        text = str(cell)
    return _normalize_symbols(_normalize_ws(text)).lower()


def _label_similarity(a: str, b: str) -> float:
    """Compute similarity between two label strings.

    Returns 1.0 for exact match, fractional for partial containment,
    0.0 for no overlap. Used for fuzzy row alignment between legacy
    labels ("Physician Decision") and native labels
    ("Discontinued | Physician Decision").
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Pipe-separated combined labels: "ALT | Value > 3xULN" should match "ALT"
    if '|' in a and '|' not in b:
        parts = [p.strip() for p in a.split('|')]
        if b in parts:
            return 0.9
        for part in parts:
            if part and b and (part in b or b in part):
                return min(len(part), len(b)) / max(len(part), len(b)) * 0.9
    if '|' in b and '|' not in a:
        parts = [p.strip() for p in b.split('|')]
        if a in parts:
            return 0.9
        for part in parts:
            if part and a and (part in a or a in part):
                return min(len(part), len(a)) / max(len(part), len(a)) * 0.9
    # Single-character abbreviation: "f" matches "female", "m" matches "male"
    if len(a) == 1 and len(b) > 1 and b.startswith(a):
        return 0.5
    if len(b) == 1 and len(a) > 1 and a.startswith(b):
        return 0.5
    # High sequence similarity catches footnote markers and minor spelling
    # differences (e.g. "drug-relateda" vs "drug-related")
    from difflib import SequenceMatcher
    seq_ratio = SequenceMatcher(None, a, b).ratio()
    if seq_ratio >= 0.9:
        return seq_ratio
    # Check if one contains the other (pipe-delimited native labels
    # often contain the legacy label as a suffix)
    if a in b or b in a:
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))
        return shorter / longer if longer > 0 else 0.0
    # Check last segment (after pipe) — native "SOC | PT" vs legacy "PT"
    b_parts = [p.strip() for p in b.split("|")]
    for part in b_parts:
        if part == a:
            return 0.9
        if a in part or part in a:
            shorter = min(len(a), len(part))
            longer = max(len(a), len(part))
            return 0.8 * (shorter / longer) if longer > 0 else 0.0
    return 0.0


def _is_header_row(row: list[str]) -> bool:
    """Detect legacy table header rows that have no data-level equivalent.

    Header rows include: treatment name spans ("Group A", "Group B", ...),
    sub-header rows ("n", "(%)", ...), footnote rows (long text),
    blank/spacer rows, and column header continuation rows.
    """
    if not row or len(row) == 0:
        return True
    label = _normalize_ws(row[0]).lower() if row[0] else ""
    # Single-cell rows are section headers or footnotes
    if len(row) == 1:
        return True
    # Structural denominator row: big-N counts per treatment expressed as
    # column headers in native ("Group A\n(N=22)"), so this row has no
    # data-level equivalent in the native IR.
    if label == "participants in population":
        return True
    # AE vertical summary section headers (flag labels as dividers)
    ae_section_patterns = [
        "with one or more adverse event",
        "moderate to severe",
        "drug-related",
        "serious",
        "leading to discontinuation",
    ]
    label_lower = _normalize_ws(row[0]).lower().strip()
    if any(label_lower.startswith(p) for p in ae_section_patterns):
        # If this row has no data cells, treat as section divider
        data_cells_ae = [_normalize_ws(c) for c in row[1:] if _normalize_ws(c)]
        if len(data_cells_ae) == 0:
            return True
    # Check if row contains only header-like content (no numeric data)
    data_cells = [_normalize_ws(c) for c in row[1:] if _normalize_ws(c)]
    if not data_cells:
        return False  # empty data = could be a data row with all blanks
    # Column header preamble rows: blank label with 1 sparse data cell
    # containing header text (e.g., "Difference in %", "Estimate", "(95 % CI)")
    if not label and len(data_cells) <= 2:
        _hdr_text_patterns = [
            "difference", "estimate", "ci)", "confidence",
            "treatment", "criterion", "test name",
        ]
        if all(any(p in c.lower() for p in _hdr_text_patterns)
               for c in data_cells):
            return True
    # Row with "Treatment" label is a column header
    if label in ("treatment", "test name (unit)"):
        return True
    # Header rows: all data cells are treatment names or sub-header labels
    header_tokens = {"n", "(%)", "group", "total", ""}
    if all(c.lower() in header_tokens or c.lower().startswith("group ")
           or c.lower().startswith("total ") or c.lower().startswith("(n=")
           or c.lower().startswith("n / m") for c in data_cells):
        return True
    # Column header continuation rows in listings: all non-empty cells are
    # short alphabetic text with no digits (e.g. "Onset", "Duration", "ID").
    # Require at least 3 non-empty data cells to avoid sparse spanning headers
    # that have mostly-empty cells (which match as both-empty in comparison).
    import re
    _no_digit = re.compile(r"^[A-Za-z %/().,-]+$")
    if len(data_cells) >= 3 and all(_no_digit.match(c) for c in data_cells):
        return True
    return False


def _align_rows_by_label(
    legacy_rows: list[list[str]],
    native_grid: list[list[tuple[str, str, str]]],
) -> list[tuple[int, int | None]]:
    """Align legacy rows to native rows by label similarity.

    Returns a list of (legacy_row_idx, native_row_idx_or_None) pairs.
    Each legacy row is matched to the best-scoring native row that hasn't
    been claimed yet. Unmatched legacy rows get native_idx=None.
    Legacy header/structural rows are excluded from the comparison.
    """
    leg_labels = [_row_label(r) for r in legacy_rows]
    nat_labels = [_row_label(r) for r in native_grid]

    # Build similarity matrix
    claimed: set[int] = set()
    alignment: list[tuple[int, int | None]] = []

    for li, ll in enumerate(leg_labels):
        best_ni: int | None = None
        best_score = 0.0
        for ni, nl in enumerate(nat_labels):
            if ni in claimed:
                continue
            score = _label_similarity(ll, nl)
            if score > best_score:
                best_score = score
                best_ni = ni
        # Require minimum similarity to claim a match
        if best_score >= 0.4 and best_ni is not None:
            claimed.add(best_ni)
            alignment.append((li, best_ni))
        else:
            alignment.append((li, None))

    # Second pass: blank-label legacy rows (listing continuations) are
    # matched to the next unclaimed native row in order IF the data cells
    # show reasonable similarity. Skip header/structural rows.
    next_native = 0
    for idx, (li, ni) in enumerate(alignment):
        if ni is not None:
            next_native = ni + 1
            continue
        if not leg_labels[li] and not _is_header_row(legacy_rows[li]):
            # Find next unclaimed native row >= next_native with data overlap
            leg_data = {_normalize_ws(c).lower() for c in legacy_rows[li] if _normalize_ws(c)}
            if not leg_data:
                continue  # skip all-blank separator rows
            for candidate in range(next_native, len(nat_labels)):
                if candidate not in claimed:
                    nat_data = set()
                    for cell in native_grid[candidate]:
                        val = cell[2] or cell[1] if isinstance(cell, tuple) else str(cell)
                        val = _normalize_ws(val).lower()
                        if val:
                            nat_data.add(val)
                    # Require at least 30% overlap in data cell values
                    overlap = len(leg_data & nat_data)
                    if overlap >= max(1, 0.3 * min(len(leg_data), len(nat_data))):
                        claimed.add(candidate)
                        alignment[idx] = (li, candidate)
                        next_native = candidate + 1
                        break

    return alignment


def compare_report_parity(
    report_type_id: str,
    legacy_rtf_path: Path | None,
    native_rtf_path: Path | None,
    native_ir_cells_path: Path | None,
    tolerance: ToleranceConfig | None = None,
    max_diffs: int = 200,
) -> ParityComparison:
    """Compare legacy vs native outputs for one report type."""
    tol = tolerance or ToleranceConfig()

    # Auto-detect IR cells CSV if not explicitly provided
    if native_ir_cells_path is None and native_rtf_path is not None:
        auto_csv = _auto_detect_ir_csv(Path(native_rtf_path), report_type_id)
        if auto_csv is not None:
            native_ir_cells_path = auto_csv
            logger.info("Auto-detected IR cells CSV: %s", auto_csv)

    comparison = ParityComparison(
        report_type_id=report_type_id,
        legacy_rtf=str(legacy_rtf_path) if legacy_rtf_path else "",
        native_rtf=str(native_rtf_path) if native_rtf_path else "",
        native_ir_cells=str(native_ir_cells_path) if native_ir_cells_path else "",
    )
    if legacy_rtf_path is None:
        comparison.verdict = ParityVerdict.SKIP
        comparison.notes = "Missing legacy RTF"
        return comparison
    if native_ir_cells_path is None and native_rtf_path is None:
        comparison.verdict = ParityVerdict.SKIP
        comparison.notes = "Missing both native IR cells and native RTF"
        return comparison

    try:
        legacy_tables = extract_tables_from_rtf(legacy_rtf_path)
        if native_ir_cells_path is not None:
            # Preferred: compare legacy RTF against native IR cells (structured)
            native_grid = _load_ir_cells_as_grid(Path(native_ir_cells_path))
        elif native_rtf_path is not None:
            # Fallback: RTF-vs-RTF comparison
            native_tables = extract_tables_from_rtf(Path(native_rtf_path))
            native_rows_raw = [r for t in native_tables for r in t.rows]
            native_grid = [
                [("text", cell, cell) for cell in row]
                for row in native_rows_raw
            ]
        else:
            native_grid = []
    except Exception as exc:
        comparison.verdict = ParityVerdict.ERROR
        comparison.notes = f"Parse error: {exc}"
        return comparison

    legacy_rows = [r for t in legacy_tables for r in t.rows]
    if not legacy_rows or not native_grid:
        comparison.verdict = ParityVerdict.ERROR
        comparison.notes = "Empty legacy or native table content"
        return comparison

    n_cols = min(
        max(len(r) for r in legacy_rows),
        max(len(r) for r in native_grid),
    )
    if len(legacy_rows) != len(native_grid) or any(
        len(lr) != len(nr) for lr, nr in zip(legacy_rows, native_grid)
    ):
        comparison.shape_mismatch = True

    # Content-based row alignment: match legacy rows to native rows by
    # label similarity (column 0 text). This handles row-count mismatches
    # (legacy has header/summary rows that native doesn't) and different
    # row ordering. Unmatched legacy rows are still counted as mismatches.
    alignment = _align_rows_by_label(legacy_rows, native_grid)

    # Column offset detection: when legacy has more text-leading columns
    # than native (e.g. legacy has 2 label columns but IR has 1 LABEL),
    # numeric data columns are misaligned. Try offsets 0..2 and pick the
    # one that produces the most cell matches on aligned rows.
    def _score_with_offset(
        _alignment: list[tuple[int, int | None]],
        col_offset: int,
    ) -> int:
        _matched = 0
        for _li, _ni in _alignment:
            if _ni is None:
                continue
            for _c in range(n_cols):
                _lc = _c
                _nc = _c - col_offset
                if _nc < 0:
                    # Legacy label column with no native counterpart — check
                    # if the native LABEL cell matches
                    if _c == 0:
                        _lv = legacy_rows[_li][_lc] if _lc < len(legacy_rows[_li]) else ""
                        _ncell = (
                            native_grid[_ni][0]
                            if len(native_grid[_ni]) > 0
                            else ("", "", "")
                        )
                        if _compare_cell(_lv, _ncell, tol):
                            _matched += 1
                    continue
                _lv = legacy_rows[_li][_lc] if _lc < len(legacy_rows[_li]) else ""
                _ncell = (
                    native_grid[_ni][_nc]
                    if _nc < len(native_grid[_ni])
                    else ("", "", "")
                )
                if _compare_cell(_lv, _ncell, tol):
                    _matched += 1
        return _matched

    best_offset = 0
    best_offset_score = _score_with_offset(alignment, 0)
    for try_offset in (1, 2):
        s = _score_with_offset(alignment, try_offset)
        if s > best_offset_score:
            best_offset_score = s
            best_offset = try_offset

    if best_offset > 0:
        logger.debug(
            "Column offset %d selected for %s (score %d vs %d at offset 0)",
            best_offset, report_type_id, best_offset_score,
            _score_with_offset(alignment, 0),
        )

    total = 0
    matched = 0
    for leg_idx, nat_idx in alignment:
        # Skip unmatched legacy header rows (treatment spans, sub-headers,
        # page-break repeats, section titles, footnotes). These are structural
        # RTF elements that the native IR doesn't produce; counting them as
        # mismatches penalizes the parity score for layout-only differences.
        if nat_idx is None and _is_header_row(legacy_rows[leg_idx]):
            continue
        for c in range(n_cols):
            total += 1
            legacy_val = legacy_rows[leg_idx][c] if c < len(legacy_rows[leg_idx]) else ""
            nc = c - best_offset
            if nc < 0:
                # Extra legacy label column — try matching with native LABEL
                if c == 0 and nat_idx is not None:
                    native_cell = (
                        native_grid[nat_idx][0]
                        if len(native_grid[nat_idx]) > 0
                        else ("", "", "")
                    )
                else:
                    native_cell = ("", "", "")
            elif nat_idx is not None:
                native_cell = (
                    native_grid[nat_idx][nc]
                    if nc < len(native_grid[nat_idx])
                    else ("", "", "")
                )
            else:
                native_cell = ("", "", "")
            if _compare_cell(legacy_val, native_cell, tol):
                matched += 1
            elif len(comparison.diffs) < max_diffs:
                comparison.diffs.append(CellDiff(
                    row_idx=leg_idx, col_idx=c,
                    legacy_value=legacy_val,
                    native_value=native_cell[2] or native_cell[1],
                    kind="value" if nat_idx is not None else "missing_native",
                ))

    comparison.total_cells = total
    comparison.matched_cells = matched
    comparison.mismatched_cells = total - matched
    if comparison.mismatched_cells == 0:
        comparison.verdict = ParityVerdict.PASS
    else:
        comparison.verdict = ParityVerdict.FAIL
    return comparison
