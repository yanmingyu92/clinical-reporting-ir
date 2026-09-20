# SCORING.md — Worksheet for Table 11 (Section 4.2.6)

Controlled IR-versus-RTF comparison. Claude Opus 4.6, temperature 0,
2026-08-11. Identical task, model, and prompt across conditions; only the
input representation varied. This worksheet derives every reported number
from the artifacts shipped in this repository — nothing is asserted without a
checkable source.

---

## Task 1 — Numeric-extraction recall (demographics): IR 90.9% vs RTF 49.1%

### Ground truth: the 55 values

The ground truth is derived from the shipped IR sample
`ai_experiment/inputs/ir_demographics_sample.json` (demographics table,
74 cells). Derivation rule (identical to the original scoring script):

> Collect every numeric token appearing in `cell_value` **or**
> `cell_formatted` of each cell, round to 4 decimal places, deduplicate.

Composition note: the shipped sample is the full table used in the
experiment (74 cells). Only 40 cells carry a non-null `cell_value`, but
combined display cells contribute two numerics each — e.g. the PERCENTAGE
cell `"53 (61.6%)"` contributes both 53 and 61.6, and the DECIMAL cell
`"75.2 (8.59)"` contributes both 75.2 and 8.59. Across all 74 cells this
yields **55 distinct numeric values**, the pre-registered ground-truth set
referenced in Section 4.2.6. (This recall metric is deliberately stricter
than the 74-cell exact-match rate reported for the feasibility demonstration
in Section 4.2.5; the two figures are not directly comparable.)

The 55 ground-truth values (sorted):

```
1.0, 1.2, 4.0, 4.3, 4.7, 6.0, 7.1, 7.89, 8.0, 8.25, 8.29, 8.59, 9.0, 9.1,
9.3, 10.7, 11.0, 14.1, 23.0, 33.0, 34.0, 38.4, 40.0, 40.5, 43.7, 44.0, 47.6,
50.0, 51.0, 52.0, 52.4, 53.0, 56.0, 56.3, 59.5, 61.6, 72.0, 74.0, 74.4, 75.1,
75.2, 75.7, 76.0, 77.5, 84.0, 85.7, 86.0, 86.6, 88.0, 88.1, 89.0, 111.0,
143.0, 220.0, 254.0
```

(14.1 originates from the table-number string "Table 14.1.1" in a HEADER
cell's `cell_formatted`; it is part of the token-extraction rule applied
uniformly to both conditions.)

### Scoring rule

A ground-truth value counts as reproduced if the response contains any
numeric token within an absolute tolerance of ±0.05. Responses scored:
`responses/task1_ir_response.txt` and `responses/task1_rtf_response.txt`
(verbatim, 2026-08-11).

### Result

| Condition | Found | Total | Recall | Missing values |
|-----------|-------|-------|--------|----------------|
| IR JSON | **50** | 55 | **90.9%** (50/55 = 90.909…%) | 1.2, 4.0, 4.3, 4.7, 11.0 |
| RTF text | **27** | 55 | **49.1%** (27/55 = 49.090…%) | 1.0, 4.0, 4.7, 8.25, 9.1, 23.0, 33.0, 34.0, 38.4, 40.0, 40.5, 43.7, 44.0, 47.6, 50.0, 52.4, 53.0, 56.3, 59.5, 61.6, 72.0, 75.1, 85.7, 86.6, 111.0, 143.0, 220.0, 254.0 |

Ratio: 90.9 / 49.1 ≈ 1.9× — the "1.9× higher numeric-extraction recall"
reported in Section 4.2.6.

Recompute from the shipped files (stdlib only):

```bash
python ai_experiment/rtf_baseline/score_baseline.py
```

---

## Task 2 — Concept recall (AE by SOC/PT): IR 5/5 vs RTF 4/5

Pre-registered set of five clinical concepts (as fixed in Section 4.2.6
before scoring):

| # | Concept | IR condition | RTF condition |
|---|---------|:------------:|:-------------:|
| 1 | Dose-response in application-site reactions | ✓ | ✓ |
| 2 | High overall AE burden in the high-dose arm | ✓ | ✗ |
| 3 | Diarrhoea non-monotonic anomaly | ✓ | ✓ |
| 4 | SOC/PT internal-consistency check | ✓ | ✓ |
| 5 | Treatment-arm imbalance | ✓ | ✓ |
|   | **Recall** | **5/5** | **4/5** |

Sources:

- **IR condition (5/5):** the verbatim response archived in
  `ai_experiment/experiment_log.md` (Experiment 2, 2026-04-24 demonstration
  run). Its five findings map one-to-one onto the pre-registered concepts.
- **RTF condition (4/5):** `responses/task2_rtf_response.txt` (2026-08-11),
  run on the RTF-extracted AE-by-SOC/PT table
  (`inputs/rtf_ae-by-soc_extracted.txt`). The response identified four of the
  five concepts; it did not identify the high overall AE burden in the
  high-dose arm as a distinct finding.

---

## Reproducibility notes

- The IR-condition inputs (`ai_experiment/inputs/*.json`) and prompts
  (`ai_experiment/prompts/*.txt`) are shared with the original feasibility
  demonstration.
- The RTF-condition inputs are pipe-delimited rows extracted from the frozen
  golden RTFs (`cdisc_pilot01/golden_outputs/PUB-DEMOGRAPHICS.rtf`,
  `PUB-AE-BY-SOC.rtf`) with the shipped extractor
  (`parity_harness.rtf_extract.extract_tables_from_rtf`), so the comparison
  targets exactly the same source tables.
- Live re-runs require an Anthropic API key; model outputs drift across API
  versions, so the archived responses are the authoritative record of the
  2026-08-11 run.
