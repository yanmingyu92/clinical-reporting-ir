"""Driver that invokes legacy SAS macros via the bridge map.

Given a ``report_type_id`` and a study context, this driver:

1. Loads the bridge entry from ``registry/legacy_bridge_map.yaml``.
2. Builds a SAS driver script that configures ``sasautos`` for the three legacy
   locations (``./``, ``./adam``, ``./submacros``) and invokes the legacy macro
   with the mapped parameter names.
3. Submits the driver via a :class:`SASComputeProvider` and captures the
   resulting RTF path.

Exactly what parameters are passed is dictated by the bridge entry's
``parameter_mapping``. Any keys the caller omits are left defaulted by the
legacy macro.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class LegacyRun:
    """Result of invoking a legacy macro via the bridge."""

    report_type_id: str
    legacy_macro: str
    status: str = "not_run"  # not_run | ok | failed
    rtf_path: Path | None = None
    log_path: Path | None = None
    return_code: int | None = None
    duration_ms: int | None = None
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class LegacyDriver:
    """Invokes a legacy bridge macro and returns the RTF path."""

    def __init__(
        self,
        bridge_map_path: Path,
        repo_root: Path,
        sas_provider: Any,
        work_dir: Path | None = None,
        *,
        legacy_libpaths: dict[str, str] | None = None,
        adam_xpt_source: str | Path | None = None,
    ) -> None:
        self._bridge_map_path = Path(bridge_map_path)
        self._repo_root = Path(repo_root).resolve()
        self._provider = sas_provider
        self._work_dir = Path(work_dir) if work_dir else None
        self._legacy_libpaths = dict(legacy_libpaths or {})
        self._adam_xpt_source = Path(adam_xpt_source) if adam_xpt_source else None
        self._bridge_map = self._load_bridge_map()

    def _load_bridge_map(self) -> dict[str, dict[str, Any]]:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load legacy_bridge_map.yaml")
        payload = yaml.safe_load(self._bridge_map_path.read_text(encoding="utf-8"))
        bridges = payload.get("legacy_bridges", []) if payload else []
        return {entry["report_type_id"]: entry for entry in bridges}

    def list_report_types(self) -> list[str]:
        return sorted(self._bridge_map.keys())

    def lookup(self, report_type_id: str) -> dict[str, Any]:
        if report_type_id not in self._bridge_map:
            raise KeyError(f"No bridge entry for report_type_id='{report_type_id}'")
        return self._bridge_map[report_type_id]

    def build_driver_sas(
        self,
        report_type_id: str,
        parameters: dict[str, Any],
        output_rtf: Path,
    ) -> str:
        """Build a SAS program that invokes the bridge macro."""
        bridge = self.lookup(report_type_id)
        legacy_macro = bridge["legacy_macro"]
        legacy_loc = bridge.get("legacy_location", "root")
        param_map = bridge.get("parameter_mapping", {}) or {}
        mapped: dict[str, str] = {}
        canonical_keys = set(param_map.keys())
        for canonical, legacy_name in param_map.items():
            if canonical in parameters:
                mapped[legacy_name] = str(parameters[canonical])
        for key, value in parameters.items():
            if key in canonical_keys:
                continue
            if key in mapped:
                continue
            mapped[key] = str(value)
        lines = [
            "/* Auto-generated parity harness driver - DO NOT EDIT */",
            f"/* report_type_id: {report_type_id} */",
            f"/* legacy_location: {legacy_loc} */",
            f"filename sasroot   '{self._repo_root.as_posix()}';",
            f"filename sasadam   '{(self._repo_root / 'adam').as_posix()}';",
            f"filename sassub   '{(self._repo_root / 'submacros').as_posix()}';",
            "options sasautos=(sasroot sasadam sassub   sasautos);",
            "options dlcreatedir;",
        ]
        for libref, libpath in self._legacy_libpaths.items():
            lines.append(f"libname {libref.lower()} '{libpath}';")
        if self._adam_xpt_source is not None:
            xpt_files = sorted(self._adam_xpt_source.glob("*.xpt"))
            for idx, xpt in enumerate(xpt_files):
                tag = f"_xpt{idx}"
                lines.append(f"libname {tag} xport '{xpt.as_posix()}' access=readonly;")
                lines.append(f"proc copy in={tag} out=lptda memtype=data; run;")
                lines.append(f"libname {tag} clear;")
        # Directory fileref so %SYSFUNC(FILEREF(fptotb))=0 in rtftable / rtftable0enhanced.
        # The legacy macros write via aggregate-member syntax (file fptotb(docfile)),
        # so fptotb must reference the *directory*, not the target RTF file.
        lines.append(f"filename fptotb '{output_rtf.parent.as_posix()}/';")
        lines += [
            f"%let parity_output_rtf = {output_rtf.as_posix()};",
        ]
        for key, value in mapped.items():
            lines.append(f"%let {key} = {value};")
        preamble_sas = bridge.get("preamble_sas")
        if preamble_sas:
            preamble_text = str(preamble_sas).strip()
            if preamble_text:
                lines.append("/* preamble_sas from bridge entry */")
                lines.append(preamble_text)
        arg_list = ", ".join(f"{k}={v}" for k, v in mapped.items())
        lines.append(f"{legacy_macro}({arg_list});")
        # ── post_calls: follow-up macro invocations (e.g. render companions) ──
        for idx, post in enumerate(bridge.get("post_calls") or []):
            if not isinstance(post, dict):
                continue
            post_macro = post["legacy_macro"]
            post_param_map = post.get("parameter_mapping", {}) or {}
            post_defaults = post.get("defaults", {}) or {}
            post_mapped: dict[str, str] = {}
            for pk, pv in post_defaults.items():
                post_mapped[pk] = str(pv)
            for canonical, legacy_name in post_param_map.items():
                if canonical in parameters:
                    post_mapped[legacy_name] = str(parameters[canonical])
            lines.append(f"/* post_calls[{idx}] from bridge entry */")
            post_arg_list = ", ".join(f"{k}={v}" for k, v in post_mapped.items())
            lines.append(f"{post_macro}({post_arg_list});")
        return "\n".join(lines) + "\n"

    def _discover_legacy_output(
        self,
        output_dir: Path,
        pre_run_files: set[Path],
        expected_rtf: Path,
        run_start_time: float | None = None,
    ) -> Path | None:
        """Locate the RTF (or extensionless RTF-equivalent) the legacy macro produced.

        With the directory-fileref convention (see build_driver_sas), the legacy
        macro controls the output filename via its internal DocFile parameter.
        This may differ from the harness's *expected_rtf* name.  We therefore
        scan *output_dir* for files that appeared or were modified after the run.

        Priority:
        1. *expected_rtf* itself (exact match — fastest path).
        2. Any new ``.rtf`` file not in *pre_run_files*.
        3. Any ``.rtf`` file modified after run_start_time (covers overwrites).
        4. Any new extensionless file not in *pre_run_files*.
        5. ``None`` — no output detected.
        """
        if expected_rtf.exists():
            return expected_rtf
        new_files = sorted(
            p for p in output_dir.iterdir()
            if p.is_file() and p not in pre_run_files
        )
        # Prefer .rtf files
        for p in new_files:
            if p.suffix.lower() == ".rtf":
                return p
        # Check for overwritten RTF files (modified after run start)
        if run_start_time is not None:
            for p in sorted(output_dir.iterdir()):
                if p.is_file() and p.suffix.lower() == ".rtf":
                    try:
                        if p.stat().st_mtime >= run_start_time:
                            return p
                    except OSError:
                        pass
        # Fall back to extensionless files (bare-fileref DocFile case)
        for p in new_files:
            if not p.suffix:
                return p
        return None

    def run(
        self,
        report_type_id: str,
        parameters: dict[str, Any],
        output_dir: Path,
    ) -> LegacyRun:
        """Run the legacy bridge macro and return a :class:`LegacyRun`."""
        bridge = self.lookup(report_type_id)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_rtf = output_dir / f"legacy_{report_type_id}.rtf"
        # Snapshot pre-existing files in output_dir so post-run discovery can
        # identify the RTF the legacy macro produced (DocFile is controlled by
        # macro-internal defaults, not by the harness output_rtf path).
        pre_run_files: set[Path] = set(output_dir.iterdir()) if output_dir.exists() else set()
        sas_code = self.build_driver_sas(report_type_id, parameters, output_rtf)

        run = LegacyRun(
            report_type_id=report_type_id,
            legacy_macro=bridge["legacy_macro"],
        )
        try:
            import time as _time
            run_start_time = _time.time()
            job = self._provider.submit_program(sas_code, f"parity_{report_type_id}")
            durable_log = output_dir / f"legacy_{report_type_id}.log"
            try:
                if job.log_path and Path(job.log_path).exists():
                    import shutil
                    shutil.copyfile(job.log_path, durable_log)
            except OSError:
                pass
            run.return_code = job.return_code
            run.duration_ms = job.duration_ms
            run.log_path = durable_log if durable_log.exists() else (
                Path(job.log_path) if job.log_path else None
            )
            produced = self._discover_legacy_output(
                output_dir, pre_run_files, output_rtf, run_start_time,
            )
            if produced is not None:
                if produced != output_rtf:
                    run.metadata["legacy_produced_filename"] = produced.name
                run.rtf_path = produced
                # SAS batch returns 0=no issues, 1=warnings only, 2+=errors.
                # Warnings are normal in production SAS runs, so accept rc<=1.
                run.status = "ok" if (job.return_code or 0) <= 1 else "failed"
            else:
                run.status = "failed"
                run.error_message = "Legacy macro did not produce RTF output"
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            logger.exception("Legacy driver failed for %s", report_type_id)
        return run
