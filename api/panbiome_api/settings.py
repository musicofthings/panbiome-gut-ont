import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    env: str
    allowed_origins: list[str]
    bucket: str
    region: str
    task_queues: list[str]
    head_queue: str
    head_log_group: str


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def load() -> Settings:
    env = os.environ.get("PANBIOME_ENV", "development")
    origins = _csv(os.environ.get("ALLOWED_ORIGINS", ""))
    if env == "production" and not origins:
        raise RuntimeError("Set ALLOWED_ORIGINS in production")
    if not origins:
        port = os.environ.get("WEB_DEV_PORT", "5173")
        origins = [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]
    return Settings(
        env=env,
        allowed_origins=origins,
        bucket=os.environ["PANBIOME_BUCKET"],
        region=os.environ.get("PANBIOME_REGION", "ap-south-1"),
        task_queues=_csv(os.environ.get("PANBIOME_TASK_QUEUES", "panbiome-default,panbiome-ondemand,panbiome-build")),
        head_queue=os.environ.get("PANBIOME_HEAD_QUEUE", "panbiome-ondemand"),
        head_log_group=os.environ.get("PANBIOME_LOG_GROUP", "/aws/batch/job"),
    )
