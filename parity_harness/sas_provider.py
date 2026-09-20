"""Minimal local SAS batch execution provider for the parity harness.

Vendored, self-contained replacement for the framework's SAS compute
infrastructure. Only the local-batch execution path is provided: programs
are submitted to a locally installed SAS executable (``sas -batch -sysin``),
which is what the legacy-side parity track needs.

If SAS is not installed or not on ``PATH``, :func:`create_sas_provider`
raises :class:`SASUnavailableError` with an instructive message.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SASUnavailableError(RuntimeError):
    """Raised when no usable SAS executable can be located."""


@dataclass
class SASJob:
    """Handle to a completed SAS batch job."""

    job_id: str
    execution_id: str
    sas_program_path: Optional[str] = None
    log_path: Optional[str] = None
    return_code: Optional[int] = None
    duration_ms: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalSASProvider:
    """Executes SAS programs in local batch mode.

    Each submission runs in an isolated working directory:
    ``sas -batch -work <dir>/saswork -log <log> -sysin <program>``.
    SAS batch return codes: 0 = clean, 1 = warnings only, 2+ = errors.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = dict(config or {})
        self._sas_executable = config.get("sas_executable", "sas")
        self._work_root = Path(config.get("work_root", tempfile.gettempdir()))
        self._timeout_seconds = int(config.get("timeout_seconds", 3600))
        resolved = shutil.which(str(self._sas_executable))
        if resolved is None:
            raise SASUnavailableError(
                f"SAS executable '{self._sas_executable}' was not found on PATH. "
                "The legacy-side parity track requires a local SAS 9.4 "
                "installation (SAS 9.4M7 was used for the manuscript runs). "
                "Install SAS or set compute.config.sas_executable in the "
                "environment YAML to the full path of your SAS executable. "
                "To inspect the frozen public-benchmark results without SAS, "
                "run: python cdisc_pilot01/run_parity.py --replay"
            )
        self._sas_executable = resolved

    def submit_program(self, sas_code: str, execution_id: str) -> SASJob:
        """Submit a SAS program for local batch execution."""
        work_dir = self._work_root / execution_id
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "saswork").mkdir(parents=True, exist_ok=True)

        program_path = work_dir / f"{execution_id}.sas"
        program_path.write_text(sas_code, encoding="utf-8")
        log_path = work_dir / f"{execution_id}.log"

        job = SASJob(
            job_id=execution_id,
            execution_id=execution_id,
            sas_program_path=str(program_path),
            log_path=str(log_path),
        )
        start_time = time.monotonic()
        try:
            result = subprocess.run(
                [
                    self._sas_executable,
                    "-batch",
                    "-work", str(work_dir / "saswork"),
                    "-log", str(log_path),
                    "-sysin", str(program_path),
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                cwd=str(work_dir),
            )
            job.return_code = result.returncode
            job.duration_ms = int((time.monotonic() - start_time) * 1000)
        except subprocess.TimeoutExpired:
            job.duration_ms = int((time.monotonic() - start_time) * 1000)
            job.return_code = -1
            logger.error(
                "SAS program timed out: execution_id=%s, timeout=%ds",
                execution_id, self._timeout_seconds,
            )
        return job


def provider_config_from_env(env_yaml: dict[str, Any]) -> dict[str, Any]:
    """Normalize an environment YAML mapping to compute/storage config.

    Returns a dict of shape::

        {"compute": {"provider": str, "config": dict},
         "storage": {"provider": str, "config": dict}}

    Accepts either an already-canonical ``compute``/``storage`` mapping or
    the nested ``environment.sas.*`` / ``environment.storage.*`` layout used
    by the environment schema in ``schema/environment.schema.json``.
    """
    env_yaml = env_yaml or {}
    if isinstance(env_yaml.get("compute"), dict):
        return {
            "compute": {
                "provider": env_yaml["compute"].get("provider", "local_batch"),
                "config": dict(env_yaml["compute"].get("config", {})),
            },
            "storage": {
                "provider": env_yaml.get("storage", {}).get("provider", "local")
                if isinstance(env_yaml.get("storage"), dict) else "local",
                "config": dict(env_yaml.get("storage", {}).get("config", {}))
                if isinstance(env_yaml.get("storage"), dict) else {},
            },
        }
    env = env_yaml.get("environment", {}) if isinstance(env_yaml, dict) else {}
    sas = env.get("sas", {}) or {}
    storage = env.get("storage", {}) or {}
    config: dict[str, Any] = {}
    if sas.get("executable"):
        config["sas_executable"] = sas["executable"]
    if sas.get("timeout_seconds"):
        config["timeout_seconds"] = sas["timeout_seconds"]
    return {
        "compute": {"provider": "local_batch", "config": config},
        "storage": {
            "provider": storage.get("provider", "local"),
            "config": dict(storage.get("config", {})),
        },
    }


def create_sas_provider(provider_type: str, config: dict[str, Any]) -> LocalSASProvider:
    """Create a SAS compute provider. Only ``local_batch`` is supported."""
    if provider_type != "local_batch":
        raise ValueError(
            f"Unknown SAS compute provider '{provider_type}'. "
            "This public package supports only 'local_batch'."
        )
    return LocalSASProvider(config)
