# Reproducibility Guide

Step-by-step instructions for reproducing every publicly reproducible result
in the manuscript (Frontiers in Pharmacology, 2026; DOI
10.3389/fphar.2026.1876207).

## Prerequisites

| Requirement | Version used in manuscript | Notes |
|-------------|---------------------------|-------|
| Python | 3.11 (3.11.7) | For the parity harness and replay verification |
| PyYAML | 6.0.x | Only third-party dependency (`pip install -r requirements.txt`) |
| SAS | 9.4M7 | **Only for legacy-side / full regeneration runs.** Not needed for the replay verification or the AI experiment. |
| Anthropic API key | — | Only for re-running the Section 4.2 LLM tasks |

Platform: the manuscript runs used Windows 10 x64; the Python components are
platform-independent.

## Install

```bash
git clone https://github.com/yanmingyu92/clinical-reporting-ir.git
cd clinical-reporting-ir
python -m venv .venv
source .venv/bin/activate      # .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## 1. Verify the Section 4.1.4.5 public-benchmark parity result (no SAS required)

```bash
python cdisc_pilot01/run_parity.py --replay
```

This re-compares the frozen golden outputs in `cdisc_pilot01/golden_outputs/`
with the comparator shipped in `parity_harness/` and prints the summary
matrix. Expected output (the Section 4.1.4.5 result, Table 8):

```
report_type_id       verdict   cells matched  mism  match%
----------------------------------------------------------
PUB-DEMOGRAPHICS     PASS        182     182     0 100.00%
PUB-AE-OVERVIEW      PASS         81      81     0 100.00%
PUB-AE-BY-SOC        PASS       2070    2070     0 100.00%
PUB-EFFICACY         PASS         16      16     0 100.00%
PUB-KM-TTDE          PASS       2415    2415     0 100.00%
----------------------------------------------------------
TOTAL                           4764    4764     0 100.00%
```

**Expected result: 5 reports, 4,764 cells, 0 mismatches, 100%
regression-consistency (all PASS).** Fresh matrix artefacts (JSON, CSV, HTML)
are written to `cdisc_pilot01/parity_output/`.

Ground-truth spot checks cited in the manuscript (Age Mean Placebo = 75.2;
N = 86/84/84) are reproducible directly from `cdisc_pilot01/sdtm_datasets/`
(`dm.xpt`, 306 records: 254 treated + 52 screen failures).

## 2. Full parity run (requires SAS 9.4)

```bash
python cdisc_pilot01/run_parity.py
```

Without a `sas` executable on `PATH` the script exits with code 2 and prints
instructions. With SAS 9.4 available (9.4M7 recommended), the script invokes
the legacy bridge macros in local batch mode via
`parity_harness.LegacyDriver`, driven by the bridge-map entries. Notes:

- The bridge map and SAS macros shipped here
  (`registry_examples/bridge_map_sample.yaml`, `registry_examples/sas_stubs/`)
  are **synthetic structural samples**. A genuine legacy-side run requires a
  real legacy macro library wired through a bridge map with the same entry
  structure; see Section 3.3.1 of the manuscript.
- The native pipeline implementation is organization-restricted and is not
  part of this repository (see `NOT_INCLUDED.md`); the native side is
  therefore supplied as frozen artifacts in `cdisc_pilot01/golden_outputs/`.
  Mode `--replay` (above) is the self-contained verification path.

## 3. Re-run the Section 4.2 AI demonstration tasks

See [`ai_experiment/README.md`](../ai_experiment/README.md). One command per
task; requires an Anthropic API key (`ANTHROPIC_API_KEY`). Recorded
conditions: Claude Opus 4.6, 2026-04-24 (API-default temperature for the
demonstration run; the controlled IR-versus-RTF comparison of 2026-08-11
used temperature 0 — see `ai_experiment/README.md`).

## 4. Inspect the schemas and validate the examples

```bash
python -m json.tool schema/ir_schema.schema.json > /dev/null   # valid JSON
python -c "import yaml; yaml.safe_load(open('registry_examples/bridge_map_sample.yaml'))"
```

A sanitized sample execution manifest conforming to
`schema/execution_manifest.schema.json` is at
[`cdisc_pilot01/execution_manifest.sample.json`](../cdisc_pilot01/execution_manifest.sample.json)
(validated against the schema; synthetic public-benchmark example with real
hashes of the shipped pilot artifacts).

The human-readable typed-cell specification is in
[`docs/IR_SCHEMA_SPEC.md`](./IR_SCHEMA_SPEC.md).

## Where each number comes from

See [`PROVENANCE.md`](../PROVENANCE.md) for the artifact-level mapping of
every headline number in the manuscript.
