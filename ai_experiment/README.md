# AI Experiment (Section 4.2) — Materials and Re-run Instructions

This directory contains everything needed to inspect and re-run the three
LLM demonstration tasks reported in Section 4.2 of the manuscript, plus the
controlled IR-versus-RTF comparison of Section 4.2.6 (Table 11) in
[`rtf_baseline/`](./rtf_baseline).

## Input provenance

The IR inputs derive from CDISCPilot01 data processed through the
framework's coexistence pathway (the underlying compute step executed by the
original legacy SAS macro, IR captured via the bridge-map adapter metadata),
curated as demonstration-sized excerpts. They reflect real pilot statistics
(e.g., Age Mean Placebo = 75.2; N = 86/84/84) but are excerpts of the full
tables, not complete study tables.

## Recorded experimental conditions

| Setting | Value |
|---------|-------|
| Model | Claude Opus 4.6 (Anthropic) |
| Temperature | API default (not specified) for the original 2026-04-24 demonstration run; **0** for the controlled IR-versus-RTF comparison (2026-08-11, `rtf_baseline/`) |
| Task / model / prompt | Identical across conditions; only the input representation varied |
| Date of run | 2026-04-24 (demonstration); 2026-08-11 (controlled comparison) |
| Framework version | modernized framework, v5.0 |
| IR schema version | 1.0 (8-field typed-cell format) |

These match the run recorded in [`experiment_log.md`](./experiment_log.md),
which also archives the verbatim model responses and the per-criterion
assessments.

## Contents

| Path | Description |
|------|-------------|
| `inputs/ir_demographics_sample.json` | Demographics table IR (T-14.1.1), 74 cells, CDISCPilot01 Safety Population |
| `inputs/ir_ae_summary_sample.json` | AE summary table IR (T-14.3.1), 80 cells, top 5 SOCs |
| `inputs/sap_tte_sample.txt` | SAP excerpt for Table 14.2.2 (time-to-event analysis) |
| `prompts/task1_summarization.txt` | Verbatim prompt for Task 1 (table → narrative) |
| `prompts/task2_anomaly_detection.txt` | Verbatim prompt for Task 2 (anomaly detection) |
| `prompts/task3_config_generation.txt` | Verbatim prompt for Task 3 (SAP → YAML config) |
| `experiment_log.md` | Full experiment log: prompts, verbatim responses, assessments |
| `rtf_baseline/` | Controlled IR-vs-RTF comparison (Section 4.2.6, Table 11): RTF-condition inputs, verbatim responses, scoring worksheet, recompute script |

Note on the Task 1 prompt: its in-prompt `cell_type` enumeration (INTEGER,
DECIMAL, PERCENTAGE, LABEL, HEADER, FOOTNOTE, EMPTY) lists the seven types
present in the demographics table; the full schema vocabulary (which also
admits `pvalue` and `text` in the SAS-side serialization) is documented in
[`../docs/IR_SCHEMA_SPEC.md`](../docs/IR_SCHEMA_SPEC.md). The prompt is
preserved verbatim as run.

## Re-running a task

An Anthropic API key is required (`ANTHROPIC_API_KEY` environment variable).
With the Python `anthropic` client installed (`pip install anthropic`), one
command per task:

```bash
python - <<'PY'
import os
from anthropic import Anthropic

task = "task1_summarization"            # or task2_anomaly_detection / task3_config_generation
input_file = {                          # input paired with each task
    "task1_summarization": "inputs/ir_demographics_sample.json",
    "task2_anomaly_detection": "inputs/ir_ae_summary_sample.json",
    "task3_config_generation": "inputs/sap_tte_sample.txt",
}[task]

prompt = open(f"prompts/{task}.txt", encoding="utf-8").read()
payload = open(f"ai_experiment/{input_file}", encoding="utf-8").read()

client = Anthropic()  # reads ANTHROPIC_API_KEY
msg = client.messages.create(
    model="claude-opus-4-6",            # exact API model ID
    max_tokens=4096,
    temperature=0,                      # 0 reproduces the controlled-comparison
                                        # conditions; the original 2026-04-24
                                        # demonstration used the API default
    messages=[{"role": "user", "content": prompt + "\n\n" + payload}],
)
print(msg.content[0].text)
PY
```

Run from the repository root. Model outputs are stochastic across API
versions; the archived responses in `experiment_log.md` (and
`rtf_baseline/responses/` for the controlled comparison) are the
authoritative record of the reported runs.

## Notes and limitations

- The IR input files are demonstration excerpts curated from CDISCPilot01 IR
  outputs (see "Input provenance" above), not complete study tables.
- A single model was evaluated; results may differ across model families.
- See the "Limitations" section of `experiment_log.md` for the full list,
  including the addendum on the controlled RTF baseline.
