import os
from datetime import UTC, datetime

os.environ.setdefault("PANBIOME_BUCKET", "test-bucket")

from fastapi.testclient import TestClient  # noqa: E402

from panbiome_api import main  # noqa: E402
from panbiome_api.aws import RunStore  # noqa: E402

TRACE = (
    "task_id\thash\tnative_id\tname\tstatus\texit\tsubmit\tduration\n"
    "1\t2f/abcd80\tj1\tVALIDATE_SAMPLESHEET\tCOMPLETED\t0\t2026-10-30 09:45:46\t3m 8s\n"
)
HEAD_CREATED = 1_793_377_000_000
LATER = datetime.fromtimestamp((HEAD_CREATED + 60_000) / 1000, UTC)
EARLIER = datetime.fromtimestamp((HEAD_CREATED - 60_000) / 1000, UTC)


def head(status, started=True):
    return {
        "jobId": "h1",
        "jobName": "panbiome-head-zymo",
        "status": status,
        "createdAt": HEAD_CREATED,
        "startedAt": HEAD_CREATED + 1000 if started else None,
        "container": {"command": ["bash", "-c", "cd /launch && { nextflow run main.nf -profile awsbatch; }"]},
    }


class FakeStore:
    def __init__(self, head=None, trace=None, params=None, jobs=()):
        self._head, self._trace, self._params, self._jobs = head, trace, params, list(jobs)

    def head_job(self, run):
        return self._head

    def head_jobs(self):
        return {"zymo": self._head} if self._head else {}

    def params(self, run):
        return self._params

    def trace(self, run):
        return self._trace

    def run_jobs(self, run, since_ms):
        return self._jobs

    def run_names(self):
        return ["zymo"]

    script = staticmethod(RunStore.script)


def client(store):
    main.app.dependency_overrides[main.store] = lambda: store
    return TestClient(main.app)


def test_health_and_cors_allows_dev_origin_only():
    c = client(FakeStore())
    ok = c.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert ok.json() == {"status": "ok"}
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_finished_run_uses_fresh_trace():
    c = client(FakeStore(head=head("SUCCEEDED"), trace=(TRACE, LATER), params=({"fastq": "x"}, LATER)))
    body = c.get("/api/runs/zymo").json()
    assert body["source"] == "trace"
    assert body["kind"] == "pipeline"
    assert body["status"] == "succeeded"
    assert body["processes"]["VALIDATE_SAMPLESHEET"]["status"] == "completed"


def test_running_run_ignores_stale_trace_and_uses_batch():
    job = {
        "jobId": "t1",
        "jobName": "INGEST_P001",
        "status": "RUNNING",
        "createdAt": HEAD_CREATED + 5000,
        "startedAt": HEAD_CREATED + 6000,
        "container": {"command": ["s3://b/work/zymo/ab/" + "c" * 30 + "/.command.run"]},
    }
    store = FakeStore(head=head("RUNNING"), trace=(TRACE, EARLIER), params=({"fastq": "x"}, EARLIER), jobs=[job])
    body = client(store).get("/api/runs/zymo").json()
    assert body["source"] == "batch"
    assert body["params"] is None
    assert body["processes"]["INGEST"]["status"] == "running"
    assert body["processes"]["VALIDATE_SAMPLESHEET"]["status"] == "pending"


def test_waiting_run_has_no_tasks():
    body = client(FakeStore(head=head("PENDING", started=False))).get("/api/runs/zymo").json()
    assert body["status"] == "waiting"
    assert body["tasks"] == []


def test_bad_run_name_and_unknown_run():
    c = client(FakeStore())
    assert c.get("/api/runs/..%2Fdb").status_code in (404, 422)
    assert c.get("/api/runs/nope").status_code == 404
