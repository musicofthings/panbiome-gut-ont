"""Read-only access to the run data in AWS Batch, S3 and CloudWatch Logs."""

import json
import re
import time
from datetime import UTC, datetime

import boto3
from botocore.config import Config

from .settings import Settings
from .tasks import filter_run_jobs

HEAD_PREFIX = "panbiome-head-"
_SCRIPT = re.compile(r"nextflow run (\S+)")


class RunStore:
    def __init__(self, settings: Settings, session: boto3.Session | None = None):
        # Explicit: boto3 does not read AWS_REGION, and the SSO profile's default region may differ.
        session = session or boto3.Session(region_name=settings.region)
        config = Config(retries={"mode": "standard", "max_attempts": 5})
        self.s = settings
        self.batch = session.client("batch", config=config)
        # Regional, virtual-hosted URLs: browsers upload to presigned URLs, and a global-endpoint URL would
        # redirect, which fails the CORS preflight.
        self.s3 = session.client(
            "s3",
            endpoint_url=f"https://s3.{settings.region}.amazonaws.com",
            config=config.merge(Config(signature_version="s3v4", s3={"addressing_style": "virtual"})),
        )
        self.logs = session.client("logs", config=config)

    # ---- S3

    def _get_text(self, key: str) -> tuple[str, datetime] | None:
        try:
            obj = self.s3.get_object(Bucket=self.s.bucket, Key=key)
        except self.s3.exceptions.NoSuchKey:
            return None
        with obj["Body"] as body:
            return body.read().decode("utf-8", "replace"), obj["LastModified"]

    def _prefixes(self, prefix: str) -> list[str]:
        pages = self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.s.bucket, Prefix=prefix, Delimiter="/")
        return [p[len(prefix) :].rstrip("/") for p in pages.search("CommonPrefixes[].Prefix") if p]

    def trace(self, run: str):
        return self._get_text(f"results/{run}/execution/trace.txt")

    def params(self, run: str) -> tuple[dict, datetime] | None:
        got = self._get_text(f"results/{run}/execution/params.json")
        return (json.loads(got[0]), got[1]) if got else None

    def reports(self, run: str) -> list[dict]:
        prefix = f"results/{run}/"
        pages = self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.s.bucket, Prefix=prefix)
        out = []
        for obj in pages.search("Contents[]"):
            if obj and obj["Key"].endswith(".html") and obj["Size"] > 0:
                url = self.s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.s.bucket, "Key": obj["Key"], "ResponseContentType": "text/html"},
                    ExpiresIn=900,
                )
                out.append({"path": obj["Key"][len(prefix) :], "size": obj["Size"], "url": url})
        return sorted(out, key=lambda r: (r["path"].count("/"), r["path"]))

    def result_text(self, run: str, path: str) -> str | None:
        got = self._get_text(f"results/{run}/{path}")
        return got[0] if got else None

    def samples(self, run: str) -> list[str]:
        return self._prefixes(f"results/{run}/samples/")

    def task_log(self, run: str, task_hash: str, lines: int) -> dict:
        listing = self.s3.list_objects_v2(Bucket=self.s.bucket, Prefix=f"work/{run}/{task_hash}", MaxKeys=1)
        if not listing.get("KeyCount"):
            return {"found": False}
        workdir = listing["Contents"][0]["Key"].rsplit("/", 1)[0]
        out = {"found": True, "workdir": f"s3://{self.s.bucket}/{workdir}/"}
        for name in (".command.sh", ".command.log", ".command.err"):
            got = self._get_text(f"{workdir}/{name}")
            out[name.lstrip(".").replace(".", "_")] = "\n".join(got[0].splitlines()[-lines:]) if got else None
        return out

    # ---- Batch

    def _list(self, queue: str, filters: list[dict]) -> list[dict]:
        pages = self.batch.get_paginator("list_jobs").paginate(jobQueue=queue, filters=filters)
        return list(pages.search("jobSummaryList[]"))

    def _describe(self, ids: list[str]) -> list[dict]:
        out = []
        for i in range(0, len(ids), 100):
            out += self.batch.describe_jobs(jobs=ids[i : i + 100])["jobs"]
        return out

    def head_jobs(self) -> dict[str, dict]:
        """Latest head job per run name, described (so the command and log stream are present)."""
        summaries = self._list(self.s.head_queue, [{"name": "JOB_NAME", "values": [HEAD_PREFIX + "*"]}])
        latest: dict[str, dict] = {}
        for j in sorted(summaries, key=lambda j: j["createdAt"]):
            latest[j["jobName"][len(HEAD_PREFIX) :]] = j
        described = self._describe([j["jobId"] for j in latest.values()])
        return {j["jobName"][len(HEAD_PREFIX) :]: j for j in described}

    def head_job(self, run: str) -> dict | None:
        summaries = self._list(self.s.head_queue, [{"name": "JOB_NAME", "values": [HEAD_PREFIX + run]}])
        if not summaries:
            return None
        latest = max(summaries, key=lambda j: j["createdAt"])
        return self._describe([latest["jobId"]])[0]

    def run_jobs(self, run: str, since_ms: int) -> list[dict]:
        filters = [{"name": "AFTER_CREATED_AT", "values": [str(since_ms - 1)]}]
        ids = [j["jobId"] for q in self.s.task_queues for j in self._list(q, filters)]
        return filter_run_jobs(self._describe(ids), run)

    def head_log(self, head: dict, lines: int) -> list[str] | None:
        stream = head.get("container", {}).get("logStreamName")
        if not stream:
            return None
        try:
            events = self.logs.get_log_events(
                logGroupName=self.s.head_log_group, logStreamName=stream, startFromHead=False, limit=lines
            )["events"]
        except self.logs.exceptions.ResourceNotFoundException:
            return None
        return [e["message"] for e in events]

    # ---- runs

    def run_names(self) -> list[str]:
        return sorted(set(self._prefixes("launch/")) | set(self._prefixes("results/")))

    @staticmethod
    def script(head: dict | None) -> str | None:
        if not head:
            return None
        m = _SCRIPT.search(" ".join(head.get("container", {}).get("command", [])))
        return m.group(1).strip("'\"") if m else None

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def iso(ms: int | None) -> str | None:
        return datetime.fromtimestamp(ms / 1000, UTC).isoformat() if ms else None
