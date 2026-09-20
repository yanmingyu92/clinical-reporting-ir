# RTF Baseline — Controlled IR-vs-RTF Comparison (Section 4.2.6, Table 11)

This directory contains the evidence package for the controlled IR-versus-RTF
comparison reported in Section 4.2.6 (Table 11) of the manuscript.

## Run record

| Setting | Value |
|---------|-------|
| Model | Claude Opus 4.6 (Anthropic; API model ID `claude-opus-4-6`) |
| Temperature | 0 |
| Date of run | 2026-08-11 |
| Design | Identical task, model, and prompt across conditions; only the input representation (typed IR JSON vs RTF-extracted text) varied |
| Metrics | Task 1: numeric-extraction recall against 55 pre-registered ground-truth values (±0.05 tolerance). Task 2: concept recall against a pre-registered set of 5 clinical concepts |

The original feasibility demonstration (2026-04-24, logged in
[`../experiment_log.md`](../experiment_log.md)) ran the IR condition only and
used the API-default temperature; this controlled comparison was run
subsequently to isolate the effect of the input representation, with
temperature fixed at 0.

## Contents

| Path | Description |
|------|-------------|
| `inputs/rtf_demographics_extracted.txt` | RTF condition input for Task 1: pipe-delimited rows extracted from the frozen golden `PUB-DEMOGRAPHICS.rtf` with the shipped extractor (`parity_harness.rtf_extract`) |
| `inputs/rtf_ae-by-soc_extracted.txt` | RTF condition input for Task 2: pipe-delimited rows extracted from `PUB-AE-BY-SOC.rtf` |
| `prompts/task1_summarization_rtf.txt` | Verbatim RTF-condition prompt for Task 1 |
| `prompts/task2_anomaly_detection_rtf.txt` | Verbatim RTF-condition prompt for Task 2 |
| `responses/task1_ir_response.txt` | Verbatim model response, Task 1, IR condition |
| `responses/task1_rtf_response.txt` | Verbatim model response, Task 1, RTF condition |
| `responses/task2_rtf_response.txt` | Verbatim model response, Task 2, RTF condition (AE by SOC/PT) |
| `results_summary.json` | Machine-readable scores and run metadata |
| `SCORING.md` | Scoring worksheet: the 55 ground-truth values and the exact 50/55 vs 27/55 arithmetic; the 5-concept Task 2 worksheet |
| `score_baseline.py` | Stdlib-only script that recomputes the Task 1 recall from the shipped files |

The IR-condition inputs are the shared samples in
[`../inputs/`](../inputs) (`ir_demographics_sample.json`,
`ir_ae_summary_sample.json`); the IR-condition prompts are in
[`../prompts/`](../prompts). The Task 2 IR-condition response is the verbatim
response archived in [`../experiment_log.md`](../experiment_log.md)
(Experiment 2).

## Recompute the Task 1 score

```bash
python ai_experiment/rtf_baseline/score_baseline.py
```

prints `IR 50/55 = 90.9%` and `RTF 27/55 = 49.1%` with the missing values per
condition.

## Re-run the comparison live

Requires an Anthropic API key (`ANTHROPIC_API_KEY`). Send each prompt with
its paired input in the message body, model `claude-opus-4-6`,
`temperature=0`, `max_tokens=2000` — same calling convention as in
[`../README.md`](../README.md). Model outputs drift across API versions; the
archived responses here are the authoritative record of the 2026-08-11 run.
