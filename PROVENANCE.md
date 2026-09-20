# Provenance of Reported Numbers

This note documents, for reviewer verifiability, which artifact in the supporting
materials each headline number in the manuscript traces to. It is deliberately
explicit about the one place where the reported metric descends from the
demonstration run rather than from a stored scoring artifact.

## Public-benchmark track (Section 4.1.4.5, Table 8 in the manuscript)

- All five public-track cell counts (182 / 81 / 2,070 / 16 / 2,415; total 4,764,
  0 mismatches) come from the parity run recorded in
  `parity_harness/` outputs against the frozen golden references in
  `cdisc_pilot01/`. The ground-truth spot checks (Age Mean Placebo = 75.2;
  N = 86/84/84) are reproducible from `cdisc_pilot01/dm.xpt` (306 records,
  86 / 84 / 84 treated + 52 screen failures).

## Real-data track (Table 5 in the manuscript)

- The per-report parity percentages (99.2 / 94.2 / ... / 65.2 / 60.4 / 44.9)
  and the effective-parity reanalysis (98.1 / 84.2 / 68.9) were computed with
  the same `parity_harness.compare` comparator shipped in this repository,
  applied to the (anonymized) legacy golden outputs and the final native
  execution artifacts of the case-study framework. The underlying real-data
  artifacts themselves are organization-restricted (see `NOT_INCLUDED.md`);
  only aggregate percentages are published. The comparator code that produced
  them is fully open here, so the methodology is reproducible end-to-end on
  the public CDISCPilot01 track.

## Controlled IR-versus-RTF comparison (Section 4.2.6, Table 11)

- **Task 1 (numeric-extraction recall, IR 90.9% = 50/55; RTF 49.1% = 27/55):**
  measured on the two verbatim model responses shipped in
  `ai_experiment/rtf_baseline/responses/` (Claude Opus 4.6, temperature 0,
  2026-08-11; identical task and prompt, only the input representation
  varied). The 55 ground-truth values are the distinct numeric tokens of the
  demographics table IR JSON (T-14.1.1, shipped in `ai_experiment/inputs/`);
  the full derivation is in `ai_experiment/rtf_baseline/SCORING.md` and is
  recomputable with `ai_experiment/rtf_baseline/score_baseline.py`.
- **Task 2, RTF condition (concept recall 4/5):** scored against the
  pre-registered five-concept set from the RTF-condition response on the
  AE-by-SOC/PT table, shipped verbatim as
  `ai_experiment/rtf_baseline/responses/task2_rtf_response.txt`; worksheet
  in `ai_experiment/rtf_baseline/SCORING.md`.
- **Task 2, IR condition (concept recall 5/5):** descends from the original
  demonstration run reported in Section 4.2 of the manuscript (the five
  findings listed in the verbatim response archived in
  `ai_experiment/experiment_log.md`, Experiment 2: dose-response in
  application-site reactions, high overall AE burden in the high-dose arm,
  dose-dependent psychiatric disorders, the diarrhoea non-monotonic
  anomaly, and the SOC/PT internal-consistency check).

## Runtime figures (Section 4.1.6, Table 9)

- Per-report medians were computed from the execution manifests of 477 valid
  real-data runs (14 report types) on the validation environment stated in
  the manuscript (SAS 9.4 TS1M7, Windows 10 x64, Python 3.11.7). The
  manifests record timestamps, return codes, and durations per run; a
  per-report summary CSV is retained in the private evidence set
  (`analysis/c1_runtime.csv`). Manifest structure is documented by the open
  `schema/execution_manifest.schema.json` in this repository.

## Person-week and cost figures (Sections 4.1.6-4.1.7)

- Explicitly labeled in the manuscript as approximate case-study estimates
  (domain-knowledge reconstruction), not measurements.

## Contact

Requests for any privately retained evidence artifact should use the contact
given in the manuscript's Data Availability statement.
