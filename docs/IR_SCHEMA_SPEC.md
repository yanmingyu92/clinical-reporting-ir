# IR Schema Specification (human-readable)

This document describes the typed-cell Intermediate Representation (IR)
contract in prose. The machine-readable definition is
[`schema/ir_schema.schema.json`](../schema/ir_schema.schema.json) (JSON
Schema draft 2020-12). Working examples are in
[`ai_experiment/inputs/`](../ai_experiment/inputs) (JSON serialization) and
[`cdisc_pilot01/golden_outputs/`](../cdisc_pilot01/golden_outputs) (CSV
serialization).

## Overview

The IR represents a rendered clinical report (table, listing, or figure) as a
flat collection of **typed cells**, plus a separate **structure** dataset
describing layout elements (titles, column headers, footnotes). It is
format-agnostic: the same IR can be rendered to RTF, PDF, HTML, or JSON, and
can be consumed directly by downstream tooling (including LLMs) without
parsing a formatted document.

## The 8 typed-cell fields

Each IR cell record carries the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `report_id` | string | Output identifier (e.g. `T-14.1.1`, `PUB-DEMOGRAPHICS`). |
| `row_id` | string/integer | Row identifier; composite of the row's group-variable values or a sequential row number. |
| `col_id` | string/integer | Column identifier (treatment arm or statistic column). |
| `cell_value` | number \| null | Raw machine-readable numeric value; `null` for text cells. This is the field downstream tools use for arithmetic (named `cell_raw_value` in the SAS-side schema). |
| `cell_formatted` | string | Display-formatted string exactly as rendered (e.g. `"75.2 (8.59)"`, `"53 (61.6%)"`). |
| `cell_type` | enum | Cell data type — see below. |
| `sort_order` | integer | Row display order within the report. |

The JSON serialization additionally carries `execution_id` (the producing
pipeline run), and the SAS-side schema adds rendering hints
(`cell_format_code`, `group_level`, `indent_level`, `spanning`,
`annotation`). These are optional for consumers.

### `cell_type` enumeration

| Value | Meaning |
|-------|---------|
| `INTEGER` | Whole-number count or value (e.g. subject counts). |
| `DECIMAL` | Continuous numeric value (e.g. mean, SD). |
| `PERCENTAGE` | A percentage, or a combined count/percent cell (`n (%)`). |
| `LABEL` | Row label identifying the parameter or category. |
| `HEADER` | Title, column header, or spanning header text. |
| `FOOTNOTE` | Footnote or metadata line. |
| `EMPTY` | Intentionally blank cell. |

(The SAS-side schema in `schema/ir_schema.schema.json` uses lowercase tokens
— `integer`, `decimal`, `percentage`, `label`, `header`, `footnote`, `empty`
— and additionally admits `pvalue` and `text`. The comparators in
`parity_harness/` accept both casings.)

## Serializations: paper JSON vs SAS-side schema vs golden CSV

The IR exists in three serializations in this repository. Field mapping:

| Paper 8-field JSON (as in `ai_experiment/inputs/*.json`) | SAS-side machine schema (`schema/ir_schema.schema.json`, 12 fields) | Golden `*_ir_cells.csv` (`cdisc_pilot01/golden_outputs/`) |
|---|---|---|
| `report_id` | `report_id` | `report_id` |
| `execution_id` | — (recorded in the execution manifest instead) | — |
| `row_id` | `row_id` | `row_id` |
| `col_id` | `col_id` | `col_id` |
| `cell_value` | `cell_raw_value` | — (not projected) |
| `cell_formatted` | `cell_formatted` | `cell_formatted` |
| `cell_type` (uppercase tokens) | `cell_type` (lowercase tokens; also `pvalue`, `text`) | `cell_type` (uppercase tokens) |
| `sort_order` | `sort_order` | `sort_order` |
| — | `cell_format_code` | — |
| — | `group_level` | — |
| — | `indent_level` | — |
| — | `spanning` | — |
| — | `annotation` | — |
| — | — | `_sub_col_order` (render-order helper) |

Notes:

- The golden `*_ir_cells.csv` files are a **projection** of the full IR: they
  carry no raw-numeric column (`cell_value`/`cell_raw_value`), which is why
  the parity comparator falls back to the formatted string when no raw value
  is present.
- In the frozen golden CSVs, some decimal statistics appear with
  `cell_type` INTEGER (e.g. the age mean 75.2 in
  `PUB-DEMOGRAPHICS_ir_cells.csv`). This is a known **cosmetic artifact of
  the frozen run's CSV export** (the type label was not re-derived on
  projection), not a schema violation; the comparator treats the
  integer/decimal/pvalue/percentage family uniformly for numeric
  comparison.

## Example

One cell of the demographics table (placebo arm, age row):

```json
{
  "report_id": "T-14.1.1",
  "row_id": 4,
  "col_id": 2,
  "cell_value": 75.2,
  "cell_formatted": "75.2 (8.59)",
  "cell_type": "DECIMAL",
  "sort_order": 7
}
```

The key design point is the **dual representation**: `cell_value` carries the
typed numeric (for computation and comparison) while `cell_formatted`
carries the exact display string (for rendering). RTF output collapses both
into one opaque string; the IR keeps them separate, which is what enables
reliable numeric extraction, cross-cell arithmetic, and tolerant parity
comparison.

## The structure dataset (`ir_structure`)

Layout metadata, one record per structural element:

| Field | Description |
|-------|-------------|
| `report_id` | Output identifier (joins to the cells). |
| `element_type` | One of `title`, `column_header`, `column_spanning_header`, `row_header`, `footnote`, `page_header`, `page_footer`. |
| `element_id` | Unique element identifier. |
| `label` | Display text of the element. |
| `order` | Display order. |
| `parent_id` | Parent element for hierarchical structures. |
| `formatting_class` | CSS-like styling class for renderers. |
| `width` | Relative column width. |
| `alignment` | `left` \| `center` \| `right` \| `decimal`. |

## Reconciliation

The schema declares a `reconciliation` block: numeric cell types
(`integer`, `decimal`, `pvalue`, `percentage`) must reconcile against the
compute output within an absolute tolerance of 1e-10 or a relative tolerance
of 1e-8 — the same tolerances the parity harness applies by default
(`parity_harness.ir_compare.ToleranceConfig`).
