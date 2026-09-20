"""Extract tabular content from RTF files produced by the legacy macros.

The legacy SAS macros emit TLFs via PROC REPORT into RTF. To compare those
outputs against the modernized-framework IR, we need to decode the RTF into a structured
list of rows and columns while discarding layout-only control words (fonts,
colors, margins, etc.).

The extractor uses a minimal, dependency-free RTF tokenizer that recognises
three structural groups:

* ``\\trowd`` / ``\\row``    - one table row
* ``\\cell``                 - end of a cell
* ``\\pard`` / ``\\par``     - paragraph markers inside a cell

All other control words are ignored. Their payload text is kept verbatim and
trimmed of whitespace. Unicode is decoded from ``\\uN`` tokens.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_CONTROL_WORD = re.compile(r"\\([a-zA-Z]+)(-?\d+)?\s?")
_UNICODE = re.compile(r"\\u(-?\d+)(?:\\'[0-9a-fA-F]{2}|[^\\{\}])?")
_HEX_ESCAPE = re.compile(r"\\'([0-9a-fA-F]{2})")


@dataclass
class RtfTable:
    """One extracted table from an RTF document.

    ``rows`` is a list of rows; each row is a list of cell strings. The first
    row is typically the column header emitted by PROC REPORT.
    """

    title: str = ""
    rows: list[list[str]] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        return max((len(r) for r in self.rows), default=0)


def _decode_unicode(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        code = int(match.group(1))
        if code < 0:
            code += 65536
        try:
            return chr(code)
        except ValueError:
            return "?"
    text = _UNICODE.sub(_replace, text)
    text = _HEX_ESCAPE.sub(
        lambda m: bytes.fromhex(m.group(1)).decode("cp1252", errors="replace"),
        text,
    )
    return text


def _tokenize(rtf: str) -> list[tuple[str, str]]:
    """Split RTF into a stream of (kind, value) tokens.

    ``kind`` is one of ``control``, ``text``, ``{``, ``}``.
    """
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(rtf)
    while i < n:
        ch = rtf[i]
        if ch in ("{", "}"):
            tokens.append((ch, ch))
            i += 1
            continue
        if ch == "\\":
            match = _CONTROL_WORD.match(rtf, i)
            if match:
                tokens.append(("control", match.group(1)))
                i = match.end()
                continue
            # Escaped character (e.g. \\ \{ \})
            if i + 1 < n:
                tokens.append(("text", rtf[i + 1]))
                i += 2
                continue
            i += 1
            continue
        if ch in ("\r", "\n"):
            i += 1
            continue
        # Plain text run up to next RTF delimiter
        j = i
        while j < n and rtf[j] not in ("\\", "{", "}", "\r", "\n"):
            j += 1
        tokens.append(("text", rtf[i:j]))
        i = j
    return tokens


def _normalize_cell(text: str) -> str:
    """Normalize whitespace in an extracted cell value.

    Collapses runs of whitespace to single spaces, strips leading/trailing
    whitespace, and removes common ODS-emitted formatting artifacts.
    """
    # Collapse multiple spaces/newlines/tabs to single space
    text = re.sub(r"\s+", " ", text).strip()
    # Remove non-breaking space (RTF \~) artifacts
    text = text.replace("\xa0", " ").strip()
    return text


def extract_tables_from_rtf(path: Path | str) -> list[RtfTable]:
    """Parse an RTF document and return every table it contains."""
    path = Path(path)
    raw = _decode_unicode(path.read_text(encoding="latin-1", errors="replace"))
    tokens = _tokenize(raw)

    tables: list[RtfTable] = []
    current_table: RtfTable | None = None
    current_row: list[str] = []
    current_cell: list[str] = []
    in_row = False

    for kind, value in tokens:
        if kind == "control":
            if value == "trowd":
                in_row = True
                current_row = []
                current_cell = []
                if current_table is None:
                    current_table = RtfTable()
            elif value == "cell" and in_row:
                current_row.append(_normalize_cell("".join(current_cell)))
                current_cell = []
            elif value == "row" and in_row:
                if current_cell:
                    current_row.append(_normalize_cell("".join(current_cell)))
                    current_cell = []
                if current_table is not None and current_row:
                    current_table.rows.append(current_row)
                current_row = []
                in_row = False
            elif value in ("par", "line"):
                current_cell.append(" ")
            elif value == "sect":
                if current_table and current_table.rows:
                    tables.append(current_table)
                current_table = None
        elif kind == "text" and in_row:
            current_cell.append(value)

    if current_table and current_table.rows:
        tables.append(current_table)

    logger.debug("Extracted %d tables from %s", len(tables), path)
    return tables
