from panbiome_api.pipeline import EDGES, PROCESS_NAMES, enabled_processes
from panbiome_api.tasks import (
    filter_run_jobs,
    parse_duration,
    rollup,
    split_job_name,
    tasks_from_jobs,
    tasks_from_trace,
)

TRACE = (
    "task_id\thash\tnative_id\tname\tstatus\texit\tsubmit\tduration\trealtime\t%cpu\tpeak_rss\n"
    "1\t2f/abcd80\tj1\tVALIDATE_SAMPLESHEET\tCOMPLETED\t0\t2026-10-30 09:45:46.630\t3m 8s\t5ms\t61%\t10 MB\n"
    "2\t7b/e6a3dd\tj2\tKRAKEN2 (P001)\tFAILED\t137\t2026-10-30 09:48:55.020\t19.4s\t3ms\t-\t-\n"
    "3\t8c/000001\tj3\tKRAKEN2 (P001)\tCOMPLETED\t0\t2026-10-30 09:50:00.000\t1h 2m\t1h\t-\t60 GB\n"
    "4\t9d/000002\tj4\tPARSE_KRAKEN (P001)\tABORTED\t-\t2026-10-30 10:50:00.000\t-\t-\t-\t-\n"
)


def cmd(run, h):
    return ["bash", "-c", f"aws s3 cp s3://bucket/work/{run}/{h}/.command.run - | bash"]


def test_split_job_name_prefers_longest_process():
    assert split_job_name("PARSE_KRAKEN_P001") == ("PARSE_KRAKEN", "P001")
    assert split_job_name("KRAKEN2_P001") == ("KRAKEN2", "P001")
    assert split_job_name("RAW_STATS_P001raw") == ("RAW_STATS", "P001raw")
    assert split_job_name("RUN_QC") == ("RUN_QC", None)
    assert split_job_name("ZYMO_ERR2906227") == ("ZYMO_ERR2906227", None)


def test_parse_duration():
    assert parse_duration("3m 8s") == 188
    assert parse_duration("1h 2m") == 3720
    assert parse_duration("5ms") == 0.005
    assert parse_duration("-") is None


def test_trace_keeps_last_attempt():
    tasks = {(t["process"], t["tag"]): t for t in tasks_from_trace(TRACE)}
    assert tasks[("KRAKEN2", "P001")]["status"] == "completed"
    assert tasks[("KRAKEN2", "P001")]["hash"] == "8c/000001"
    assert tasks[("KRAKEN2", "P001")]["peak_rss"] == "60 GB"
    assert tasks[("PARSE_KRAKEN", "P001")]["status"] == "failed"
    assert tasks[("PARSE_KRAKEN", "P001")]["exit"] is None
    assert tasks[("VALIDATE_SAMPLESHEET", None)]["duration_s"] == 188


def test_jobs_filtered_by_run_and_latest_attempt_wins():
    h1, h2 = "48/" + "a" * 30, "49/" + "b" * 30
    jobs = [
        {
            "jobId": "a",
            "jobName": "FLYE_P001",
            "status": "FAILED",
            "createdAt": 1000,
            "startedAt": 1000,
            "stoppedAt": 3000,
            "container": {"command": cmd("zymo", h1), "exitCode": 1},
        },
        {
            "jobId": "b",
            "jobName": "FLYE_P001",
            "status": "RUNNING",
            "createdAt": 4000,
            "startedAt": 5000,
            "container": {"command": cmd("zymo", h2)},
        },
        {
            "jobId": "c",
            "jobName": "FLYE_P001",
            "status": "SUCCEEDED",
            "createdAt": 4500,
            "container": {"command": cmd("zymo-old", h2)},
        },
    ]
    mine = filter_run_jobs(jobs, "zymo")
    assert [j["jobId"] for j in mine] == ["a", "b"]
    (task,) = tasks_from_jobs(mine, now_ms=8000)
    assert task["status"] == "running"
    assert task["hash"] == h2
    assert task["duration_s"] == 3


def test_rollup_precedence_and_skipped():
    enabled = {"KRAKEN2", "BRACKEN", "FLYE"}
    tasks = [
        {"process": "KRAKEN2", "status": "completed"},
        {"process": "KRAKEN2", "status": "queued"},
        {"process": "FLYE", "status": "failed"},
        {"process": "FLYE", "status": "running"},
    ]
    r = rollup(tasks, enabled)
    assert r["KRAKEN2"]["status"] == "running"
    assert r["FLYE"]["status"] == "failed"
    assert r["BRACKEN"]["status"] == "pending"
    assert r["EMU"]["status"] == "skipped"


def test_enabled_processes_follow_main_nf_rules():
    zymo = {
        "assay": "shotgun",
        "kraken2_db": "k",
        "sylph_db": "s",
        "checkm2_db": "c",
        "genomad_db": "g",
        "eggnog_db": "e",
        "gtdbtk_db": None,
        "skip_host_depletion": False,
    }
    on = enabled_processes(zymo)
    assert {"HOST_DEPLETION", "KRAKEN2", "SYLPH", "MEDAKA", "SEMIBIN2", "CHECKM2", "GENOMAD", "EGGNOG"} <= on
    assert not on & {"HOST_SKIP", "EMU", "GTDBTK", "UNPOLISHED_CONTIGS"}
    s16 = enabled_processes({"assay": "16s", "emu_db": "x", "skip_host_depletion": True})
    assert {"EMU", "HOST_SKIP"} <= s16
    assert not s16 & {"KRAKEN2", "FLYE", "HOST_DEPLETION"}
    assert enabled_processes(None) == set(PROCESS_NAMES)


def test_edges_reference_known_processes():
    assert {n for e in EDGES for n in e} <= set(PROCESS_NAMES)
