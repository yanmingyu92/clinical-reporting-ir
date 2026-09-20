"""Top-level orchestrator for the modernized-framework parity harness.

For every report type the caller selects, the harness:

1. Invokes the legacy bridge macro via :class:`LegacyDriver`.
2. Invokes the modernized-framework native pipeline via :class:`NativeDriver`.
3. Compares their outputs with :func:`compare_report_parity`.
4. Builds a :class:`ParityMatrixEntry` for each report type.
5. Writes the pass/fail matrix in JSON / CSV / HTML via
   :func:`write_parity_matrix`.

All paths and knobs are supplied either via the CLI or via a YAML run
configuration - nothing is hardcoded.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from .ir_compare import ToleranceConfig

from .compare import ParityVerdict, compare_report_parity
from .legacy_driver import LegacyDriver, LegacyRun
from .matrix import ParityMatrixEntry, write_parity_matrix
from .native_driver import NativeDriver

logger = logging.getLogger(__name__)

# Run modes recognised by the harness.
#   "both_sides"  - run legacy bridge + native pipeline (default; public-benchmark track).
#   "native_only" - run native pipeline only; resolve the legacy-side RTF from a
#                   pre-existing golden archive via golden_rtf_index_path. Used by
#                   the real-data track to skip ~60 min/cycle of legacy SAS.
MODE_BOTH_SIDES = "both_sides"
MODE_NATIVE_ONLY = "native_only"
_VALID_MODES = (MODE_BOTH_SIDES, MODE_NATIVE_ONLY)


@dataclass
class ParityRunConfig:
    """Configuration required to run the parity harness."""

    repo_root: Path
    bridge_map_path: Path
    study_config_dir: Path
    core_registry_dir: Path
    environment_config_path: Path
    output_root: Path
    parity_output_dir: Path
    report_type_ids: list[str]
    tolerance_abs: float = 1e-10
    tolerance_rel: float = 1e-8
    tolerance_mode: str = "either"
    legacy_parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    legacy_id_map: dict[str, str] = field(default_factory=dict)
    mode: str = MODE_BOTH_SIDES
    golden_rtf_index_path: Path | None = None
    legacy_call_registry_path: Path | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> "ParityRunConfig":
        if yaml is None:
            raise RuntimeError("PyYAML is required to read parity config")
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        mode = str(data.get("mode", MODE_BOTH_SIDES))
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid mode '{mode}' in {path}; expected one of {_VALID_MODES}"
            )
        golden_idx = data.get("golden_rtf_index")
        legacy_reg = data.get("legacy_call_registry")
        return cls(
            repo_root=Path(data["repo_root"]),
            bridge_map_path=Path(data["bridge_map_path"]),
            study_config_dir=Path(data["study_config_dir"]),
            core_registry_dir=Path(data["core_registry_dir"]),
            environment_config_path=Path(data["environment_config_path"]),
            output_root=Path(data["output_root"]),
            parity_output_dir=Path(data["parity_output_dir"]).absolute(),
            report_type_ids=list(data.get("report_type_ids", [])),
            tolerance_abs=float(data.get("tolerance_abs", 1e-10)),
            tolerance_rel=float(data.get("tolerance_rel", 1e-8)),
            tolerance_mode=str(data.get("tolerance_mode", "either")),
            legacy_parameters=data.get("legacy_parameters", {}) or {},
            legacy_id_map=dict(data.get("legacy_id_map", {}) or {}),
            mode=mode,
            golden_rtf_index_path=Path(golden_idx) if golden_idx else None,
            legacy_call_registry_path=Path(legacy_reg) if legacy_reg else None,
        )


class ParityHarness:
    """Runs legacy + native pipelines and emits a parity matrix."""

    def __init__(self, config: ParityRunConfig, sas_provider: Any) -> None:
        self._config = config
        # Legacy-side construction is only required for the both_sides track.
        # In native_only mode the harness resolves the legacy RTF from a
        # pre-existing golden archive (golden_rtf_index.yaml) and never invokes
        # SAS for the legacy path, so the provider may be None.
        if config.mode == MODE_NATIVE_ONLY:
            self._legacy = None
            self._golden_rtf_index = self._load_golden_rtf_index()
            self._golden_rtf_root = self._load_golden_rtf_root()
        else:
            libpaths = self._load_legacy_libpaths()
            xpt_src = self._detect_adam_xpt_source()
            if xpt_src is not None:
                adam_target = config.parity_output_dir / "legacy_work" / "adam_sas7bdat"
                adam_target.mkdir(parents=True, exist_ok=True)
                libpaths["lptda"] = adam_target.as_posix()
            self._legacy = LegacyDriver(
                bridge_map_path=config.bridge_map_path,
                repo_root=config.repo_root,
                sas_provider=sas_provider,
                work_dir=config.parity_output_dir / "legacy_work",
                legacy_libpaths=libpaths,
                adam_xpt_source=xpt_src,
            )
            self._golden_rtf_index = {}
            self._golden_rtf_root = None
        self._native = NativeDriver(
            study_config_dir=config.study_config_dir,
            core_registry_dir=config.core_registry_dir,
            environment_config_path=config.environment_config_path,
            output_root=config.output_root,
        )
        self._tolerance = ToleranceConfig(
            absolute=config.tolerance_abs,
            relative=config.tolerance_rel,
            mode=config.tolerance_mode,
        )

    def _load_golden_rtf_index(self) -> dict[str, dict[str, Any]]:
        """Load golden_rtf_index.yaml and key entries by their bridge_key.

        Returns an empty dict (fail-open) if the path is unset, missing, or
        the file does not declare any entries — callers will surface a SKIP
        verdict per report when the lookup misses.
        """
        idx_path = self._config.golden_rtf_index_path
        if idx_path is None or yaml is None:
            return {}
        # Resolve relative paths against repo_root for symmetry with bridge_map_path.
        resolved = idx_path if idx_path.is_absolute() else (
            self._config.repo_root / idx_path
        )
        if not resolved.exists():
            return {}
        try:
            payload = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for entry in payload.get("entries", []) or []:
            key = entry.get("bridge_key")
            if key:
                out[str(key)] = entry
        return out

    def _load_golden_rtf_root(self) -> Path | None:
        """Resolve environment.storage.config.golden_rtf_root from the env YAML."""
        try:
            if yaml is None:
                return None
            env_path = Path(self._config.environment_config_path)
            if not env_path.exists():
                return None
            env = yaml.safe_load(env_path.read_text(encoding="utf-8")) or {}
            root = env["environment"]["storage"]["config"].get("golden_rtf_root")
            if not root:
                return None
            return Path(root)
        except (KeyError, TypeError, OSError):
            return None

    def _resolve_golden_rtf(
        self, report_type_id: str, legacy_id: str,
    ) -> tuple[Path | None, str]:
        """Locate the golden RTF for ``legacy_id`` (bridge key).

        Returns ``(rtf_path | None, error_message)``.  ``rtf_path`` is None
        when the index or root is unconfigured, the entry is missing, or the
        file does not exist on disk.
        """
        if not self._golden_rtf_index:
            return None, "golden_rtf_index not configured or empty"
        entry = self._golden_rtf_index.get(legacy_id)
        if entry is None:
            return None, f"No golden_rtf_index entry for bridge_key='{legacy_id}'"
        rtf_name = entry.get("rtf")
        if not rtf_name:
            return None, f"golden_rtf_index entry '{legacy_id}' has no 'rtf' field"
        # Prefer environment-config root; fall back to relative golden_root in the index.
        root = self._golden_rtf_root
        if root is None:
            return None, "golden_rtf_root not set in environment YAML"
        candidate = root / rtf_name
        if not candidate.exists():
            return None, f"golden RTF not found on disk: {candidate}"
        return candidate, ""

    def _build_native_only_legacy_run(
        self, report_type_id: str, legacy_id: str,
    ) -> LegacyRun:
        """Synthesise a LegacyRun pointing at the indexed golden RTF."""
        rtf_path, err = self._resolve_golden_rtf(report_type_id, legacy_id)
        legacy_macro = ""
        entry = self._golden_rtf_index.get(legacy_id) if self._golden_rtf_index else None
        if entry:
            legacy_macro = f"%{entry.get('macro', '')}"
        run = LegacyRun(
            report_type_id=report_type_id,
            legacy_macro=legacy_macro,
        )
        if rtf_path is None:
            run.status = "failed"
            run.error_message = err
        else:
            run.status = "ok"
            run.rtf_path = rtf_path
            run.metadata["golden_rtf_root"] = str(self._golden_rtf_root)
            run.metadata["bridge_key"] = legacy_id
        return run

    def _detect_adam_xpt_source(self) -> str | None:
        """Return adam_path if it exists and contains .xpt files, else None."""
        try:
            if yaml is None:
                return None
            env_path = Path(self._config.environment_config_path)
            if not env_path.exists():
                return None
            env = yaml.safe_load(env_path.read_text(encoding="utf-8")) or {}
            adam = env["environment"]["storage"]["config"]["adam_path"]
            adam_p = Path(adam)
            if not adam_p.exists():
                return None
            has_xpt = any(adam_p.glob("*.xpt"))
            return str(adam_p) if has_xpt else None
        except (KeyError, TypeError, OSError):
            return None

    def _load_legacy_libpaths(self) -> dict[str, str]:
        """Extract {lptda, lptop} paths from env YAML.

        Returns empty dict on any missing key (fail-open).
        """
        try:
            if yaml is None:
                return {}
            env_path = Path(self._config.environment_config_path)
            if not env_path.exists():
                return {}
            env = yaml.safe_load(env_path.read_text(encoding="utf-8")) or {}
            storage_cfg = env["environment"]["storage"]["config"]
            return {
                "lptda": str(storage_cfg["adam_path"]),
                "lptop": str(storage_cfg["output_root"]),
            }
        except (KeyError, TypeError, OSError):
            return {}

    def run(self) -> list[ParityMatrixEntry]:
        entries: list[ParityMatrixEntry] = []
        legacy_dir = self._config.parity_output_dir / "legacy_rtf"
        native_only = self._config.mode == MODE_NATIVE_ONLY
        for report_type_id in self._config.report_type_ids:
            legacy_id = self._config.legacy_id_map.get(report_type_id, report_type_id)
            params = (self._config.legacy_parameters or {}).get(report_type_id, {})
            if native_only:
                legacy_run = self._build_native_only_legacy_run(report_type_id, legacy_id)
            else:
                legacy_run = self._legacy.run(legacy_id, params, legacy_dir)
            native_run = self._native.run(report_type_id)
            comparison = compare_report_parity(
                report_type_id=report_type_id,
                legacy_rtf_path=legacy_run.rtf_path,
                native_rtf_path=native_run.rtf_path,
                native_ir_cells_path=native_run.ir_cells_path,
                tolerance=self._tolerance,
            )
            if legacy_run.status != "ok":
                comparison.verdict = ParityVerdict.ERROR
                comparison.notes = f"Legacy driver: {legacy_run.error_message}"
            elif native_run.status != "ok":
                comparison.verdict = ParityVerdict.ERROR
                comparison.notes = f"Native driver: {native_run.error_message}"
            entries.append(ParityMatrixEntry.from_comparison(comparison))
            logger.info(
                "Parity %s: %s (%.2f%%)",
                report_type_id, comparison.verdict, comparison.match_pct,
            )
        return entries


def run_parity_suite(
    config: ParityRunConfig,
    sas_provider: Any,
    run_label: str = "parity",
) -> dict[str, Path]:
    """Convenience entry point: run harness and emit matrix artefacts."""
    harness = ParityHarness(config, sas_provider)
    entries = harness.run()
    return write_parity_matrix(
        entries=entries,
        output_dir=config.parity_output_dir,
        run_label=run_label,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path,
                        help="YAML file describing the parity run.")
    parser.add_argument("--report-ids", nargs="*", default=None,
                        help="Run only these report IDs (subset of config).")
    parser.add_argument("--run-label", default="parity",
                        help="Prefix for the parity matrix output files.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    config = ParityRunConfig.from_yaml(args.config)
    if args.report_ids:
        config.report_type_ids = [
            rid for rid in args.report_ids
            if rid in config.report_type_ids or rid in config.legacy_id_map
        ]
        if not config.report_type_ids:
            logger.error("None of --report-ids matched config: %s", args.report_ids)
            return 1
    from .sas_provider import create_sas_provider, provider_config_from_env
    env_yaml = (
        yaml.safe_load(
            config.environment_config_path.read_text(encoding="utf-8")
        ) or {}
    ) if yaml else {}
    normalized = provider_config_from_env(env_yaml)
    try:
        provider = create_sas_provider(
            normalized["compute"]["provider"],
            normalized["compute"]["config"],
        )
    except Exception as exc:
        logger.error("%s", exc)
        return 2
    outputs = run_parity_suite(config, provider, run_label=args.run_label)
    logger.info("Parity matrix artefacts: %s", outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
