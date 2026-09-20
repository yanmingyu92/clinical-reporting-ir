# clinical-reporting-ir

**Reproducibility package** accompanying the paper:

> Jaime Yan. *"A Non-Destructive Methodological Framework for Modernizing
> Legacy Clinical Reporting Systems for AI-Driven Pharmacoinformatics: A SAS
> Case Study."* **Frontiers in Pharmacology** (2026).
> DOI: [10.3389/fphar.2026.1876207](https://doi.org/10.3389/fphar.2026.1876207)
> — Manuscript ID 1876207.

**Author:** Jaime Yan, Department of Data Science, Harrisburg University of
Science and Technology, Harrisburg, PA, United States —
[myan7@my.harrisburgu.edu](mailto:myan7@my.harrisburgu.edu)

---

## What this repository contains

This package provides every methodological component of the paper that does
**not** depend on proprietary industrial source code: the formal Intermediate
Representation (IR) schema, the YAML configuration specification, and the
parity validation harness, together with a complete public-benchmark
implementation on the CDISC CDISCPilot01 pilot study and the Section 4.2 AI
experiment materials.

| Directory | Contents | Paper section |
|-----------|----------|---------------|
| [`schema/`](./schema) | JSON Schemas: IR (`ir_schema.schema.json`), report type, study config, execution manifest, execution plan, environment | §3.2 |
| [`registry_examples/`](./registry_examples) | Synthetic anonymized bridge-map sample (`bridge_map_sample.yaml`), structural SAS stubs (`sas_stubs/`), public golden-RTF index, two example report YAML configs | §3.2, §3.3.1 |
| [`parity_harness/`](./parity_harness) | Python harness: legacy/native drivers, RTF extractor, cell comparator, summary matrix, vendored tolerance config and local SAS provider | §3.3.2–3.3.4 |
| [`cdisc_pilot01/`](./cdisc_pilot01) | Full public-benchmark implementation: study config, 22 SDTM `.xpt` datasets, frozen golden outputs, one-command runner, sample execution manifest | §4.1.4.5 (public track, Table 8) |
| [`ai_experiment/`](./ai_experiment) | Prompts, IR JSON inputs, and the experiment log for the three LLM tasks (summarization, anomaly detection, config generation) | §4.2 |
| [`docs/`](./docs) | Human-readable IR schema spec; step-by-step reproducibility guide | — |

See [`docs/REPRODUCIBILITY_GUIDE.md`](./docs/REPRODUCIBILITY_GUIDE.md) for
full installation and run instructions.

---

## Quick start

```bash
# 1. Environment (Python 3.11; see docs/REPRODUCIBILITY_GUIDE.md)
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Verify the §4.1.4.5 public-benchmark parity result — no SAS required:
#    5 reports, 4,764 cells, 0 mismatches, 100% regression-consistency
python cdisc_pilot01/run_parity.py --replay

# 3. Inspect an IR JSON sample consumed by the LLM (§4.2)
cat ai_experiment/inputs/ir_demographics_sample.json

# 4. Re-run an LLM task (§4.2) — requires an Anthropic API key;
#    see ai_experiment/README.md for the one-command re-run
```

A **full** parity run (legacy-side SAS execution) requires a local SAS 9.4
installation: `python cdisc_pilot01/run_parity.py`. Without SAS it exits with
a message explaining the requirement and the `--replay` alternative.

---

## What is **not** included

The industrial framework implementation, the internal legacy SAS library, the
PROT008-SR1 real-data inputs, and organization-specific registry entries are
**not** in this repository. This is an organizational-policy restriction, not
a methodological gap: the paper's contribution is the **methodology**
(evaluation framework, layered architecture, bridge map, typed IR, parity
harness), every component of which is reproducible from the materials in this
repository against the public CDISC CDISCPilot01 benchmark. The industrial
case study is presented as evidence of scale, not as the reusable artifact.
Full details in [`NOT_INCLUDED.md`](./NOT_INCLUDED.md); artifact-level
traceability of every reported number is in
[`PROVENANCE.md`](./PROVENANCE.md).

---

## License

- Code, schemas, and documentation: [MIT](./LICENSE) © 2026 Jaime Yan.
- CDISC SDTM pilot datasets (`cdisc_pilot01/sdtm_datasets/`): upstream CDISC
  terms — see [`DATA_LICENSE.md`](./DATA_LICENSE.md).

## Citation

If you use this package, please cite the paper (see [`CITATION.cff`](./CITATION.cff)):

> Yan J. A Non-Destructive Methodological Framework for Modernizing Legacy
> Clinical Reporting Systems for AI-Driven Pharmacoinformatics: A SAS Case
> Study. *Frontiers in Pharmacology* (2026).
> DOI: 10.3389/fphar.2026.1876207.
