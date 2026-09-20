# Frozen golden outputs — CDISCPilot01 public-benchmark track

These are the frozen reference outputs from the public-benchmark parity run
behind Section 4.1.4.5 (Table 8) of the manuscript (5 reports, 4,764 cells, 0 mismatches,
100% regression-consistency).

| File | Role |
|------|------|
| `PUB-*.rtf` (5 files) | Golden RTF outputs; serve as the legacy-side oracle (self-referencing golden baseline) and, for PUB-KM-TTDE, as the frozen native RTF |
| `PUB-*_ir_cells.csv` (4 files) | Frozen native IR cell exports (typed-cell IR serialized to CSV) |
| `PUB-*_ir_structure.csv` (4 files) | Frozen native IR structure (layout) exports |

PUB-KM-TTDE is a Kaplan-Meier figure and has no IR cell export; its parity
check compares RTF-to-RTF.

## Re-verifying without SAS

```bash
python cdisc_pilot01/run_parity.py --replay
```

re-compares these frozen artifacts with the shipped comparator
(`parity_harness.compare_report_parity`) and writes a fresh parity matrix
(JSON/CSV/HTML) to `cdisc_pilot01/parity_output/`.

## Regenerating from source

Regenerating the golden outputs from the SDTM datasets requires a SAS 9.4
environment (9.4M7 was used for the manuscript runs) and the reporting
pipeline configuration under `cdisc_pilot01/config/`. See
`docs/REPRODUCIBILITY_GUIDE.md`.
