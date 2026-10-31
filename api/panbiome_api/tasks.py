"""Turn Nextflow trace rows and AWS Batch job descriptions into one task list, and roll tasks up per process."""

import csv
import io
import re
from datetime import UTC, datetime

from .pipeline import PROCESS_NAMES

BATCH_STATUS = {
    "SUBMITTED": "queued",
    "PENDING": "queued",
    "RUNNABLE": "queued",
    "STARTING": "queued",
    "RUNNING": "running",
    "SUCCEEDED": "completed",
    "FAILED": "failed",
}
TRACE_STATUS = {"COMPLETED": "completed", "CACHED": "completed", "FAILED": "failed", "ABORTED": "failed"}

_BY_LENGTH = sorted(PROCESS_NAMES, key=len, reverse=True)
_DURATION_PART = re.compile(r"([\d.]+)(ms|s|m|h|d)")
_UNIT_SECONDS = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
_WORKDIR = re.compile(r"/work/[^/]+/([0-9a-f]{2}/[0-9a-f]{30})/\.command\.run")


def split_job_name(name: str) -> tuple[str, str | None]:
    """Batch job names are the task name with spaces and brackets folded to '_', e.g. KRAKEN2_P001."""
    for p in _BY_LENGTH:
        if name == p:
            return p, None
        if name.startswith(p + "_"):
            return p, name[len(p) + 1 :]
    return name, None


def split_trace_name(name: str) -> tuple[str, str | None]:
    m = re.fullmatch(r"(.+?) \((.*)\)", name)
    return (m.group(1), m.group(2)) if m else (name, None)


def parse_duration(text: str) -> float | None:
    parts = _DURATION_PART.findall(text or "")
    return sum(float(v) * _UNIT_SECONDS[u] for v, u in parts) if parts else None


def _iso_ms(ms: int | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat() if ms else None


def tasks_from_trace(text: str) -> list[dict]:
    """Last attempt of each task in a Nextflow trace.txt."""
    latest: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        latest[row["name"]] = row
    tasks = []
    for name, row in latest.items():
        process, tag = split_trace_name(name)
        tasks.append(
            {
                "process": process,
                "tag": tag,
                "status": TRACE_STATUS.get(row["status"], row["status"].lower()),
                "submitted": row.get("submit") or None,
                "duration_s": parse_duration(row.get("duration", "")),
                "peak_rss": row.get("peak_rss") or None,
                "exit": row.get("exit") if row.get("exit") not in ("", "-") else None,
                "hash": row.get("hash"),
                "job_id": row.get("native_id"),
            }
        )
    return tasks


def filter_run_jobs(jobs: list[dict], run: str) -> list[dict]:
    """Batch jobs whose command runs a task under work/<run>/."""
    marker = f"/work/{run}/"
    return [j for j in jobs if marker in " ".join(j.get("container", {}).get("command", []))]


def tasks_from_jobs(jobs: list[dict], now_ms: int) -> list[dict]:
    """Latest Batch job per task name, from describe_jobs output."""
    latest: dict[str, dict] = {}
    for j in sorted(jobs, key=lambda j: j["createdAt"]):
        latest[j["jobName"]] = j
    tasks = []
    for name, j in latest.items():
        process, tag = split_job_name(name)
        started, stopped = j.get("startedAt"), j.get("stoppedAt")
        m = _WORKDIR.search(" ".join(j.get("container", {}).get("command", [])))
        exit_code = j.get("container", {}).get("exitCode")
        tasks.append(
            {
                "process": process,
                "tag": tag,
                "status": BATCH_STATUS.get(j["status"], j["status"].lower()),
                "submitted": _iso_ms(j["createdAt"]),
                "duration_s": ((stopped or now_ms) - started) / 1000 if started else None,
                "peak_rss": None,
                "exit": str(exit_code) if exit_code is not None else None,
                "hash": m.group(1) if m else None,
                "job_id": j["jobId"],
                "reason": j.get("statusReason"),
            }
        )
    return tasks


_PRECEDENCE = ["failed", "running", "queued", "completed"]


def rollup(tasks: list[dict], enabled: set[str]) -> dict[str, dict]:
    """Per-process status: failed, then running (or partly done), then queued, then completed.
    A process with no tasks is pending, or skipped when the run's params leave it out."""
    out = {p: {"status": "pending" if p in enabled else "skipped", "counts": {}} for p in PROCESS_NAMES}
    for t in tasks:
        entry = out.setdefault(t["process"], {"status": "pending", "counts": {}})
        entry["counts"][t["status"]] = entry["counts"].get(t["status"], 0) + 1
    for entry in out.values():
        counts = entry["counts"]
        for s in _PRECEDENCE:
            if counts.get(s):
                entry["status"] = s
                break
        if entry["status"] == "queued" and counts.get("completed"):
            entry["status"] = "running"
    return out
