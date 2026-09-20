# What Is NOT Included — and Why

This document makes the reproducibility boundary explicit, in direct response to Reviewer 3 (#4: "clarify which components will be publicly accessible upon publication") and Reviewer 2 (#3, #13).

## Included (public, in this repository)

- The Intermediate Representation (IR) JSON Schema — `schema/ir_schema.schema.json`
- The YAML configuration specifications (report type, study config) — `schema/`
- The parity validation harness (legacy/native drivers, comparator, matrix) — `parity_harness/`
- An anonymized bridge-map sample (7 synthetic entries) — `registry_examples/bridge_map_sample.yaml`
- The public-benchmark golden RTF index — `registry_examples/golden_rtf_index_public.yaml`
- Two illustrative public-benchmark report configs — `registry_examples/report_config_examples/`
- The complete CDISC CDISCPilot01 public-benchmark implementation — `cdisc_pilot01/`
- The frozen golden outputs of the §4.1.4.5 public-track parity run — `cdisc_pilot01/golden_outputs/`
- Synthetic structural SAS stubs paired with bridge-map entries — `registry_examples/sas_stubs/`
- The Section 4.2 LLM demonstration inputs, prompts, and log — `ai_experiment/`

## Withheld (organization-restricted; NOT in this repository)

| Artifact | Reason | Manuscript treatment |
|----------|--------|----------------------|
| Industrial framework source (`src/sas/`, `src/python/`) | Organizational IP policy | Methodology described framework-agnostically (§3.2); contribution is the method, not this code |
| Internal legacy SAS library (`adam/`, `submacros/`, `real_data/`, `derived-utils/`) | Validated regulatory asset; cannot be redistributed | Case-study metrics reported in aggregate (§4.1); library characterized via the evaluation framework (§3.1) |
| PROT008-SR1 real-data inputs and outputs | Anonymized industry-internal Phase III dataset | Only aggregate parity percentages published; data-access contact provided in Data Availability statement |
| Organization-specific registry entries (`adam_templates/` non-pilot, `paramn_lookup/`, internal report configs) | Encode organization-specific conventions | Discussed as non-generalizable in §5.2 |
| `environment_real.yaml` | Contains internal paths, libnames, server references | A sanitized sample environment config (`cdisc_pilot01/config/environment.yaml`) is included instead |

## Justification

The manuscript's central claim is a **methodology**, not a software product: the evaluation framework, the layered architecture pattern, the bridge-map concept, the typed IR contract, and the parity-validation harness. Each of these is fully reproducible from the included materials against the public CDISC CDISCPilot01 benchmark. The industrial case study (§4.1) demonstrates that the methodology scales to a 558-component library, but the reusable scientific contribution does not depend on that specific library being available.

The non-destructive adoption pattern (§3.2.7) is, by design, the component most likely to transfer to other organizations without requiring access to this organization's source: it depends only on well-defined legacy macro entry points, which any adopter already has for their own library.

We acknowledge in §5.5 that the proprietary boundary limits independent reproduction of the **industrial-scale** results; the public-benchmark track (§4.1.4.5) is provided precisely to give reviewers an externally verifiable, independently runnable demonstration of the methodology.
