import os
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("PANBIOME_BUCKET", "test-bucket")

import boto3  # noqa: E402
import pytest  # noqa: E402
from botocore.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from panbiome_api import main, report  # noqa: E402
from panbiome_api.files import MIN_PART, FileStore, part_size  # noqa: E402

NOW = datetime(2026, 11, 1, tzinfo=UTC)


class FakeS3:
    """Enough of an S3 client for FileStore; presigned URLs come from a real client with dummy keys."""

    def __init__(self, keys=()):
        self.objects = {k: b"x" * 10 for k in keys}
        self.uploads = {}
        self.signer = boto3.Session(aws_access_key_id="a", aws_secret_access_key="b", region_name="ap-south-1").client(
            "s3",
            endpoint_url="https://s3.ap-south-1.amazonaws.com",
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

    def generate_presigned_url(self, *a, **kw):
        return self.signer.generate_presigned_url(*a, **kw)

    def list_objects_v2(self, Bucket, Prefix, Delimiter=None, MaxKeys=1000, ContinuationToken=None):
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        if Delimiter:
            folders = sorted({Prefix + k[len(Prefix) :].split("/")[0] + "/" for k in keys if "/" in k[len(Prefix) :]})
            keys = [k for k in keys if "/" not in k[len(Prefix) :]]
        else:
            folders = []
        return {
            "CommonPrefixes": [{"Prefix": f} for f in folders],
            "Contents": [{"Key": k, "Size": len(self.objects[k]), "LastModified": NOW} for k in keys[:MaxKeys]],
        }

    def put_object(self, Bucket, Key, Body, Metadata=None):
        self.objects[Key] = Body

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def create_multipart_upload(self, Bucket, Key, Metadata):
        self.uploads["u1"] = (Key, Metadata)
        return {"UploadId": "u1"}

    def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload):
        assert self.uploads[UploadId][0] == Key
        self.objects[Key] = b"done"
        self.completed = MultipartUpload["Parts"]

    def abort_multipart_upload(self, Bucket, Key, UploadId):
        self.uploads.pop(UploadId)


def client(s3):
    main.app.dependency_overrides[main.files] = lambda: FileStore(s3, "test-bucket")
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _clear():
    yield
    main.app.dependency_overrides.clear()


def test_listing_splits_folders_and_files():
    s3 = FakeS3(["uploads/run1/", "uploads/run1/a.fastq.gz", "uploads/run1/sub/b.bam", "uploads/top.csv"])
    c = client(s3)
    top = c.get("/api/files", params={"root": "uploads"}).json()
    assert top["folders"] == ["run1"] and [f["name"] for f in top["files"]] == ["top.csv"] and top["writable"]
    inner = c.get("/api/files", params={"root": "uploads", "path": "run1"}).json()
    assert inner["path"] == "run1/" and inner["folders"] == ["sub"]
    assert [f["name"] for f in inner["files"]] == ["a.fastq.gz"]


@pytest.mark.parametrize("path", ["../launch", "a/../../x", "a//b/./c", "a\\b"])
def test_paths_cannot_leave_their_root(path):
    r = client(FakeS3()).get("/api/files", params={"root": "uploads", "path": path})
    assert r.status_code == 400


def test_read_only_roots_reject_writes():
    c = client(FakeS3())
    assert c.post("/api/uploads", json={"root": "results", "path": "x.txt", "size": 5}).status_code == 403
    assert c.post("/api/files/folders", json={"root": "launch", "path": "x"}).status_code == 404
    assert c.delete("/api/files", params={"root": "results", "path": "r/x.html"}).status_code == 403


def test_download_url_is_regional_and_an_attachment():
    c = client(FakeS3(["results/run/report.html"]))
    url = c.get("/api/files/download", params={"root": "results", "path": "run/report.html"}).json()["url"]
    u = urlparse(url)
    assert u.netloc == "test-bucket.s3.ap-south-1.amazonaws.com" and u.path == "/results/run/report.html"
    assert parse_qs(u.query)["response-content-disposition"] == ['attachment; filename="report.html"']
    assert c.get("/api/files/download", params={"root": "results", "path": "run/nope"}).status_code == 404


def test_multipart_upload_round_trip():
    s3 = FakeS3()
    c = client(s3)
    size = 3 * MIN_PART + 5
    start = c.post("/api/uploads", json={"root": "uploads", "path": "run2/reads.fastq.gz", "size": size}).json()
    assert start["key"] == "uploads/run2/reads.fastq.gz" and start["parts"] == 4
    assert s3.uploads["u1"][1] == {"uploaded-by": "local"}
    urls = c.post("/api/uploads/parts", json={"key": start["key"], "upload_id": "u1", "part_numbers": [1, 2]}).json()
    q = parse_qs(urlparse(urls["urls"]["2"]).query)
    assert q["partNumber"] == ["2"] and q["uploadId"] == ["u1"]
    parts = [{"part_number": n, "etag": f'"e{n}"'} for n in (2, 1, 4, 3)]
    done = c.post("/api/uploads/complete", json={"key": start["key"], "upload_id": "u1", "parts": parts})
    assert done.status_code == 200
    assert [p["PartNumber"] for p in s3.completed] == [1, 2, 3, 4]
    again = c.post("/api/uploads", json={"root": "uploads", "path": "run2/reads.fastq.gz", "size": 1})
    assert again.status_code == 409


def test_part_urls_only_for_uploads():
    c = client(FakeS3())
    r = c.post("/api/uploads/parts", json={"key": "results/x", "upload_id": "u1", "part_numbers": [1]})
    assert r.status_code == 403


def test_part_size_keeps_under_ten_thousand_parts():
    assert part_size(1) == MIN_PART
    big = 300 * 1024**3
    assert big / part_size(big) <= 10_000


def test_empty_file_and_folders():
    s3 = FakeS3()
    c = client(s3)
    assert c.post("/api/uploads", json={"root": "uploads", "path": "e.txt", "size": 0}).json()["upload_id"] is None
    assert "uploads/e.txt" in s3.objects
    c.post("/api/files/folders", json={"root": "uploads", "path": "new run"})
    assert "uploads/new run/" in s3.objects
    s3.objects["uploads/new run/x"] = b"1"
    r = c.delete("/api/files", params={"root": "uploads", "path": "new run", "folder": True})
    assert r.status_code == 409
    del s3.objects["uploads/new run/x"]
    assert c.delete("/api/files", params={"root": "uploads", "path": "new run", "folder": True}).status_code == 200


def test_parse_tsv_types_and_header_hash():
    rows = report.parse_tsv("#rname\tdepth\tflag\tid\nc1\t7.5\tTrue\t007\nc2\tNA\tFalse\t12\n")
    assert rows == [
        {"rname": "c1", "depth": 7.5, "flag": True, "id": "007"},
        {"rname": "c2", "depth": None, "flag": False, "id": 12},
    ]


def test_sample_report_keeps_and_sorts_species():
    files = {
        "samples/S1/taxonomy/S1.species.tsv": (
            "taxon\tkept\tfinal_rel_abundance\nA\tTrue\t0.1\nB\tFalse\t0.5\nC\tTrue\t0.3\n"
        ),
        "samples/S1/qc/S1.host.json": '{"host_reads": 3}',
    }
    got = report.sample_report(files.get, "S1")
    assert [r["taxon"] for r in got["species"]["rows"]] == ["C", "A"]
    assert got["species"]["kept"] == 2 and got["species"]["candidates"] == 3
    assert got["host"] == {"host_reads": 3} and got["bins"] is None and got["amr"] is None
