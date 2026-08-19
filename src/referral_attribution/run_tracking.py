"""Optional local run evidence for resumable and auditable execution."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
from typing import Any

import pandas as pd


def utc_now() -> str:
    """Return a stable UTC timestamp for run evidence."""
    return datetime.now(timezone.utc).isoformat()


def default_run_id() -> str:
    """Create a filesystem-safe run identifier."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_run_id(run_id: str | None) -> str:
    """Reject run IDs that could escape the local runs directory."""
    candidate = (run_id or default_run_id()).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", candidate):
        raise ValueError(
            "run_id may contain only letters, numbers, dot, underscore, and hyphen."
        )
    return candidate


def sha256_file(path: Path) -> str:
    """Hash a file without loading it entirely into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RunTracker:
    """Write concise local inventory, event, checkpoint, and summary files."""

    def __init__(self, project_root: Path, run_id: str | None = None) -> None:
        self.project_root = project_root.resolve()
        self.run_id = normalize_run_id(run_id)
        self.run_root = self.project_root / "runs" / self.run_id
        self.logs_dir = self.run_root / "logs"
        self.checkpoints_dir = self.run_root / "checkpoints"
        self.artifacts_dir = self.run_root / "artifacts"
        self.summaries_dir = self.run_root / "summaries"

        for path in [
            self.logs_dir,
            self.checkpoints_dir,
            self.artifacts_dir,
            self.summaries_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        stage: str,
        action: str,
        status: str,
        note: str,
        target_file: str = "",
        command: str = "",
        exit_code: int = 0,
    ) -> None:
        """Append one concise machine-readable event."""
        record = {
            "ts": utc_now(),
            "run_id": self.run_id,
            "stage": stage,
            "action": action,
            "target_file": target_file,
            "command": command,
            "status": status,
            "exit_code": exit_code,
            "note": note,
        }
        with (self.logs_dir / "agent.jsonl").open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def write_command(self, command: str) -> None:
        """Append a human-readable command record."""
        with (self.logs_dir / "commands.log").open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(f"{utc_now()}  {command}\n")

    def write_inventory(self, paths: list[Path]) -> Path:
        """Record relative file metadata and hashes without copying data."""
        files = []
        for path in sorted(paths):
            stat = path.stat()
            files.append(
                {
                    "relative_path": path.resolve()
                    .relative_to(self.project_root)
                    .as_posix(),
                    "size_bytes": stat.st_size,
                    "modified_at_utc": datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                    "sha256": sha256_file(path),
                }
            )
        inventory = {
            "run_id": self.run_id,
            "created_at": utc_now(),
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
            "files": files,
        }
        path = self.run_root / "inventory.json"
        path.write_text(
            json.dumps(inventory, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return path

    def write_plan(self) -> Path:
        """Write the fixed local execution stages for this run."""
        path = self.run_root / "plan.md"
        path.write_text(
            "\n".join(
                [
                    f"# Run Plan: {self.run_id}",
                    "",
                    "1. Load and validate the accepted configuration.",
                    "2. Inventory source files without copying row-level data.",
                    "3. Normalize, filter, match, classify, and reconcile.",
                    "4. Write deterministic derived outputs.",
                    "5. Validate accepted regression values and booking IDs.",
                    "6. Record a checkpoint and concise summary.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return path

    def write_checkpoint(
        self,
        stage: str,
        started_at: str,
        regression: dict[str, int],
        output_files: list[str],
        blockers: list[str] | None = None,
    ) -> Path:
        """Record a resumable stage result without row-level data."""
        checkpoint = {
            "stage": stage,
            "started_at": started_at,
            "finished_at": utc_now(),
            "files_created_or_refreshed": sorted(output_files),
            "tests_run": [],
            "regression_snapshot": regression,
            "next_step": "Run pytest and review manager-facing artifacts.",
            "blockers": blockers or [],
        }
        path = self.checkpoints_dir / f"{stage}.json"
        path.write_text(
            json.dumps(checkpoint, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return path

    def write_summary(self, regression: dict[str, int]) -> Path:
        """Write a concise human-readable run summary."""
        path = self.summaries_dir / "pipeline.md"
        lines = [
            f"# Pipeline Summary: {self.run_id}",
            "",
            f"- Eligible bookings: {regression['eligible_bookings']}",
            f"- Strict honored: {regression['strict_honored']}",
            f"- Primary review: {regression['primary_review']}",
            f"- Tier A / B / C: {regression['tier_a']} / {regression['tier_b']} / {regression['tier_c']}",
            f"- Reverse-time source disagreements: {regression['reverse_time_source_disagreement']}",
            "",
            "No row-level source data is copied into this run folder.",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def write_failure(self, stage: str, error: Exception) -> None:
        """Record a failed tracked run before the exception is re-raised."""
        self.log_event(
            stage=stage,
            action="pipeline",
            status="error",
            note=f"{type(error).__name__}: {error}",
            exit_code=1,
        )
        path = self.checkpoints_dir / f"{stage}_error.json"
        path.write_text(
            json.dumps(
                {
                    "stage": stage,
                    "finished_at": utc_now(),
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "next_step": "Diagnose the deterministic failure before retrying.",
                },
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
