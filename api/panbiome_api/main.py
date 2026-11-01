"""Run monitor API: runs on AWS Batch, their step graph, task status, logs and reports, plus a file explorer
for the data bucket with direct browser-to-S3 uploads."""

from datetime import datetime
from typing import Annotated

from botocore.exceptions import ClientError, NoCredentialsError, TokenRetrievalError
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import pipeline, report, settings
from .aws import RunStore
from .files import ROOTS, FileStore
from .tasks import rollup, tasks_from_jobs, tasks_from_trace

HEAD_STATUS = {
    "SUBMITTED": "waiting",
    "PENDING": "waiting",
    "RUNNABLE": "starting",
    "STARTING": "starting",
    "RUNNING": "running",
    "SUCCEEDED": "succeeded",
    "FAILED": "failed",
}
FINISHED = {"SUCCEEDED", "FAILED"}

config = settings.load()
app = FastAPI(title="panbiome-gut-ont run monitor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

_store: RunStore | None = None


def store() -> RunStore:
    global _store
    if _store is None:
        _store = RunStore(config)
    return _store


def files() -> FileStore:
    s = store()
    return FileStore(s.s3, s.s.bucket)


Store = Annotated[RunStore, Depends(store)]
Files = Annotated[FileStore, Depends(files)]
RunName = Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]{1,100}$")]
SampleName = Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]{1,100}$")]


def user_of(request: Request) -> str:
    """The signed-in user from the API Gateway JWT authorizer; "local" when running with uvicorn."""
    event = request.scope.get("aws.event") or {}
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    return str(claims.get("username") or claims.get("sub") or "local")


@app.exception_handler(TokenRetrievalError)
@app.exception_handler(NoCredentialsError)
async def credentials_expired(request: Request, exc: Exception):
    return JSONResponse({"detail": "AWS credentials are missing or expired. Run: aws sso login"}, status_code=503)


@app.exception_handler(ClientError)
async def aws_error(request: Request, exc: ClientError):
    return JSONResponse({"detail": f"AWS error: {exc.response['Error'].get('Message', str(exc))}"}, status_code=502)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/pipeline")
def pipeline_graph():
    return pipeline.graph()


def _is_pipeline(script: str | None, params: dict | None) -> bool:
    return script == "main.nf" or (script is None and bool(params and params.get("fastq")))


def _head_fields(head: dict | None) -> dict:
    if not head:
        return {"status": None, "reason": None, "created": None, "started": None, "stopped": None, "head_job_id": None}
    return {
        "status": HEAD_STATUS.get(head["status"], head["status"].lower()),
        "reason": head.get("statusReason"),
        "created": RunStore.iso(head.get("createdAt")),
        "started": RunStore.iso(head.get("startedAt")),
        "stopped": RunStore.iso(head.get("stoppedAt")),
        "head_job_id": head["jobId"],
    }


def _fresh(modified: datetime | None, head: dict | None) -> bool:
    """A file under results/<run>/ belongs to the latest attempt only if written after its head job was created."""
    return modified is not None and (head is None or modified.timestamp() * 1000 >= head["createdAt"])


@app.get("/api/runs")
def list_runs(s: Store):
    heads = s.head_jobs()
    runs = []
    for name in s.run_names():
        head = heads.get(name)
        row = {"name": name, "script": RunStore.script(head), **_head_fields(head)}
        if head is None:
            trace = s.trace(name)
            if trace:
                failed = any(t["status"] == "failed" for t in tasks_from_trace(trace[0]))
                row.update(status="failed" if failed else "succeeded", stopped=trace[1].isoformat())
            else:
                row["status"] = "unknown"
        runs.append(row)
    return sorted(runs, key=lambda r: r["created"] or r["stopped"] or "", reverse=True)


@app.get("/api/runs/{run}")
def get_run(run: RunName, s: Store):
    head = s.head_job(run)
    script = RunStore.script(head)
    got_params = s.params(run)
    params = got_params[0] if got_params and _fresh(got_params[1], head) else None
    trace = s.trace(run)

    if trace and _fresh(trace[1], head) and (head is None or head["status"] in FINISHED):
        source, tasks = "trace", tasks_from_trace(trace[0])
    elif head and head.get("startedAt"):
        source, tasks = "batch", tasks_from_jobs(s.run_jobs(run, head["createdAt"]), RunStore.now_ms())
    else:
        source, tasks = "none", []

    if head is None and source == "none" and run not in s.run_names():
        raise HTTPException(404, f"No run named {run}")

    fields = _head_fields(head)
    if head is None and source == "trace":
        failed = any(t["status"] == "failed" for t in tasks)
        fields.update(status="failed" if failed else "succeeded", stopped=trace[1].isoformat())
    elif fields["status"] is None:
        fields["status"] = "unknown"

    is_pipeline = _is_pipeline(script, params)
    return {
        "name": run,
        "script": script,
        "kind": "pipeline" if is_pipeline else "utility",
        **fields,
        "source": source,
        "params": params,
        "processes": rollup(tasks, pipeline.enabled_processes(params)) if is_pipeline else None,
        "tasks": sorted(tasks, key=lambda t: (t["submitted"] or "", t["process"], t["tag"] or "")),
    }


@app.get("/api/runs/{run}/log")
def run_log(run: RunName, s: Store, lines: Annotated[int, Query(ge=10, le=2000)] = 300):
    head = s.head_job(run)
    if head is None:
        note = "No head job in AWS Batch for this run (Batch keeps finished jobs for about 7 days)."
        return {"lines": None, "note": note}
    got = s.head_log(head, lines)
    return {"lines": got, "note": None if got is not None else "The head job has not written a log yet."}


@app.get("/api/runs/{run}/tasks/log")
def task_log(
    run: RunName,
    s: Store,
    hash: Annotated[str, Query(pattern=r"^[0-9a-f]{2}/[0-9a-f]{6,30}$")],
    lines: Annotated[int, Query(ge=10, le=2000)] = 200,
):
    return s.task_log(run, hash, lines)


@app.get("/api/runs/{run}/reports")
def reports(run: RunName, s: Store):
    return s.reports(run)


@app.get("/api/runs/{run}/samples")
def run_samples(run: RunName, s: Store):
    return report.run_summary(lambda path: s.result_text(run, path), s.samples(run))


@app.get("/api/runs/{run}/samples/{sample}")
def sample_report(run: RunName, sample: SampleName, s: Store):
    if sample not in s.samples(run):
        raise HTTPException(404, f"No sample {sample} in {run}")
    return report.sample_report(lambda path: s.result_text(run, path), sample)


# ---- file explorer

RootName = Annotated[str, Query(pattern=r"^[a-z_]{1,30}$")]


@app.get("/api/files/roots")
def file_roots():
    return [{"name": k, "label": r.label, "writable": r.writable} for k, r in ROOTS.items()]


@app.get("/api/files")
def list_files(f: Files, root: RootName, path: str = "", token: str | None = None):
    return f.listing(root, path, token)


@app.get("/api/files/download")
def download(f: Files, root: RootName, path: str):
    return f.download_url(root, path)


@app.get("/api/files/view")
def view(f: Files, root: RootName, path: str):
    return f.view_url(root, path)


@app.delete("/api/files")
def delete_file(f: Files, root: RootName, path: str, folder: bool = False):
    return f.delete(root, path, folder)


class FolderIn(BaseModel):
    root: str
    path: str


@app.post("/api/files/folders")
def make_folder(body: FolderIn, f: Files):
    return f.make_folder(body.root, body.path)


class UploadIn(BaseModel):
    root: str
    path: str
    size: int
    overwrite: bool = False


class PartsIn(BaseModel):
    key: str
    upload_id: str
    part_numbers: list[int]


class Part(BaseModel):
    part_number: int
    etag: str


class CompleteIn(BaseModel):
    key: str
    upload_id: str
    parts: list[Part] = Field(max_length=10_000)


class AbortIn(BaseModel):
    key: str
    upload_id: str


@app.post("/api/uploads")
def start_upload(body: UploadIn, f: Files, request: Request):
    return f.start_upload(body.root, body.path, body.size, body.overwrite, user_of(request))


@app.post("/api/uploads/parts")
def upload_parts(body: PartsIn, f: Files):
    return f.part_urls(body.key, body.upload_id, body.part_numbers)


@app.post("/api/uploads/complete")
def complete_upload(body: CompleteIn, f: Files):
    return f.complete(body.key, body.upload_id, [p.model_dump() for p in body.parts])


@app.post("/api/uploads/abort")
def abort_upload(body: AbortIn, f: Files):
    return f.abort(body.key, body.upload_id)
