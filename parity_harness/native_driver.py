"""Driver that invokes the modernized-framework native pipeline for a single report type.

The parity harness uses this driver to produce the "new system" output that
will be compared against the legacy bridge run. All runs are isolated by
execution id so that concurrent parity tests do not interfere with each
other.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NativeRun:
    """Result of running the modernized-framework native pipeline for one report type."""

    report_type_id: str
    status: str = "not_run"  # not_run | ok | failed | skipped
    execution_id: str = ""
    ir_cells_path: Path | None = None
    ir_structure_path: Path | None = None
    rtf_path: Path | None = None
    log_path: Path | None = None
    duration_ms: int | None = None
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class NativeDriver:
    """Runs the modernized-framework pipeline for a single report type.

    The driver is deliberately thin: it wraps :class:`PipelineExecutor` and
    post-processes the execution result into a :class:`NativeRun` with the
    specific artifact paths the parity comparator needs.
    """

    def __init__(
        self,
        study_config_dir: Path,
        core_registry_dir: Path,
        environment_config_path: Path,
        output_root: Path,
    ) -> None:
        self._study_config_dir = Path(study_config_dir)
        self._core_registry_dir = Path(core_registry_dir)
        self._environment_config_path = Path(environment_config_path)
        self._output_root = Path(output_root)

    def run(self, report_type_id: str) -> NativeRun:
        """Report that native pipeline execution is unavailable here.

        The native pipeline executor is part of the industrial framework
        implementation, which is NOT included in this public repository
        (see NOT_INCLUDED.md). On the public benchmark track, native-side
        artifacts are instead supplied as frozen references under
        ``cdisc_pilot01/golden_outputs/`` and compared via
        ``python cdisc_pilot01/run_parity.py --replay``.
        """
        run = NativeRun(report_type_id=report_type_id)
        run.status = "failed"
        run.error_message = (
            "Native pipeline execution is not available in this public "
            "repository (the framework implementation is "
            "organization-restricted; see NOT_INCLUDED.md). Use the frozen "
            "golden outputs: python cdisc_pilot01/run_parity.py --replay"
        )
        logger.error("Native driver unavailable for %s", report_type_id)
        self._persist_failure_log(run, None, None)
        return run

    def _persist_failure_log(
        self,
        run: NativeRun,
        result: Any,
        tb_text: str | None,
    ) -> None:
        """Write a triage log capturing traceback + step-level diagnostics.

        Mirrors the legacy driver convention: ``native_<report_type_id>.log``
        co-located with the configured ``output_root`` so the parity harness
        and downstream triage can locate it without knowing the execution id.
        Best-effort: a write failure does not propagate and does not change
        ``run.status``.
        """
        try:
            self._output_root.mkdir(parents=True, exist_ok=True)
            log_path = self._output_root / f"native_{run.report_type_id}.log"
            lines: list[str] = []
            lines.append("=== Native pipeline triage log ===")
            lines.append(
                f"timestamp: {datetime.now(timezone.utc).isoformat()}"
            )
            lines.append(f"report_type_id: {run.report_type_id}")
            lines.append(f"execution_id: {run.execution_id or '<none>'}")
            lines.append(f"status: {run.status}")
            lines.append(f"error_message: {run.error_message}")
            lines.append("")
            if tb_text:
                lines.append("--- Python traceback ---")
                lines.append(tb_text.rstrip())
                lines.append("")
            if result is not None:
                lines.append("--- Pipeline result ---")
                lines.append(f"result.status: {getattr(result, 'status', '?')}")
                lines.append(
                    f"total_steps={getattr(result, 'total_steps', 0)} "
                    f"completed={getattr(result, 'completed_steps', 0)} "
                    f"failed={getattr(result, 'failed_steps', 0)} "
                    f"skipped={getattr(result, 'skipped_steps', 0)}"
                )
                steps = getattr(result, "step_results", []) or []
                for sr in steps:
                    lines.append("")
                    lines.append(
                        f"step output_id={getattr(sr, 'output_id', '?')} "
                        f"step_id={getattr(sr, 'step_id', '?')} "
                        f"status={getattr(sr, 'status', '?')} "
                        f"return_code={getattr(sr, 'return_code', None)} "
                        f"duration_ms={getattr(sr, 'duration_ms', None)}"
                    )
                    sas_path = getattr(sr, "sas_program_path", None)
                    if sas_path:
                        lines.append(f"  sas_program_path: {sas_path}")
                    sas_log = getattr(sr, "log_path", None)
                    if sas_log:
                        lines.append(f"  sas_log_path: {sas_log}")
                    err = getattr(sr, "error_message", None)
                    if err:
                        lines.append(f"  error_message: {err}")
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            run.log_path = log_path
            run.metadata["log_path"] = str(log_path)
        except OSError as log_exc:  # pragma: no cover - best-effort persistence
            logger.warning(
                "Failed to persist native triage log for %s: %s",
                run.report_type_id, log_exc,
            )

    def _load_environment(self) -> dict[str, Any]:
        try:
            import yaml
        except ImportError:  # pragma: no cover
            raise RuntimeError("PyYAML is required to load the environment YAML")
        return yaml.safe_load(
            self._environment_config_path.read_text(encoding="utf-8")
        ) or {}

    def _find_rendered_output(
        self, execution_id: str, report_type_id: str,
    ) -> Path | None:
        """Locate the rendered RTF for a report type within the execution dir."""
        base = self._output_root / execution_id
        if not base.exists():
            return None
        for ext in (".rtf", ".pdf", ".html"):
            direct = base / "output" / f"{report_type_id}{ext}"
            if direct.exists():
                return direct
        matches = list(base.glob(f"**/*{report_type_id}*.rtf"))
        return matches[0] if matches else None
