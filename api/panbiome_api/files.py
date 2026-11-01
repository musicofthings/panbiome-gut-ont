"""File explorer over the data bucket: browse, download, and direct browser-to-S3 multipart uploads."""

import math
import re
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException

# S3 allows 10,000 parts per upload; parts are at least 5 MiB except the last.
MIN_PART = 16 * 1024 * 1024
MAX_PARTS = 10_000
MAX_SIZE = 5 * 1024**4
URL_SECONDS = 3600
_SEGMENT = re.compile(r"^[^\x00-\x1f\x7f/\\]{1,255}$")


@dataclass(frozen=True)
class Root:
    prefix: str
    label: str
    writable: bool


ROOTS = {
    "uploads": Root("uploads/", "Uploads", True),
    "results": Root("results/", "Results", False),
    "test_data": Root("test_data/", "Test data", False),
}


def root_of(name: str, write: bool = False) -> Root:
    root = ROOTS.get(name)
    if root is None:
        raise HTTPException(404, f"No file area named {name}")
    if write and not root.writable:
        raise HTTPException(403, f"{root.label} is read-only")
    return root


def clean_path(path: str, folder: bool = False) -> str:
    """A relative path inside a root: no empty, '.', '..' or control-character segments."""
    parts = path.strip("/").split("/") if path.strip("/") else []
    for p in parts:
        if p in (".", "..") or not _SEGMENT.match(p):
            raise HTTPException(400, f"Invalid path segment: {p!r}")
    joined = "/".join(parts)
    if len(joined.encode()) > 900:
        raise HTTPException(400, "Path is too long")
    if not folder and not joined:
        raise HTTPException(400, "A file path is required")
    return joined + "/" if folder and joined else joined


def part_size(size: int) -> int:
    mib = 1024 * 1024
    return max(MIN_PART, math.ceil(size / MAX_PARTS / mib) * mib)


class FileStore:
    def __init__(self, s3, bucket: str):
        self.s3 = s3
        self.bucket = bucket

    def _exists(self, key: str) -> bool:
        # A listing rather than HeadObject: the API role may list only some prefixes, and HeadObject on a
        # missing key then answers 403 instead of 404.
        got = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=key, MaxKeys=1)
        return any(o["Key"] == key for o in got.get("Contents", []))

    def listing(self, root_name: str, path: str, token: str | None) -> dict:
        root = root_of(root_name)
        prefix = root.prefix + clean_path(path, folder=True)
        args = {"Bucket": self.bucket, "Prefix": prefix, "Delimiter": "/", "MaxKeys": 1000}
        if token:
            args["ContinuationToken"] = token
        page = self.s3.list_objects_v2(**args)
        folders = [p["Prefix"][len(prefix) :].rstrip("/") for p in page.get("CommonPrefixes", [])]
        files = [
            {"name": o["Key"][len(prefix) :], "size": o["Size"], "modified": _iso(o["LastModified"])}
            for o in page.get("Contents", [])
            if o["Key"] != prefix  # the folder's own marker
        ]
        return {
            "root": root_name,
            "path": prefix[len(root.prefix) :],
            "writable": root.writable,
            "folders": sorted(folders, key=str.lower),
            "files": sorted(files, key=lambda f: f["name"].lower()),
            "next_token": page.get("NextContinuationToken"),
        }

    def download_url(self, root_name: str, path: str) -> dict:
        key = root_of(root_name).prefix + clean_path(path)
        if not self._exists(key):
            raise HTTPException(404, "File not found")
        name = key.rsplit("/", 1)[-1].replace('"', "")
        url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key, "ResponseContentDisposition": f'attachment; filename="{name}"'},
            ExpiresIn=URL_SECONDS,
        )
        return {"url": url}

    def view_url(self, root_name: str, path: str) -> dict:
        """Opens an HTML report in a new tab instead of downloading it."""
        key = root_of(root_name).prefix + clean_path(path)
        if not key.endswith(".html"):
            raise HTTPException(400, "Only HTML reports can be viewed")
        url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key, "ResponseContentType": "text/html"},
            ExpiresIn=URL_SECONDS,
        )
        return {"url": url}

    def make_folder(self, root_name: str, path: str) -> dict:
        rel = clean_path(path, folder=True)
        if not rel:
            raise HTTPException(400, "A folder name is required")
        key = root_of(root_name, write=True).prefix + rel
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=b"")
        return {"path": key}

    def delete(self, root_name: str, path: str, folder: bool) -> dict:
        root = root_of(root_name, write=True)
        key = root.prefix + clean_path(path, folder=folder)
        if folder:
            listing = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=key, MaxKeys=2)
            if any(o["Key"] != key for o in listing.get("Contents", [])):
                raise HTTPException(409, "The folder is not empty")
        elif not self._exists(key):
            raise HTTPException(404, "File not found")
        self.s3.delete_object(Bucket=self.bucket, Key=key)
        return {"deleted": key}

    # ---- multipart upload, with the browser sending each part straight to S3

    def start_upload(self, root_name: str, path: str, size: int, overwrite: bool, user: str) -> dict:
        key = root_of(root_name, write=True).prefix + clean_path(path)
        if size < 0 or size > MAX_SIZE:
            raise HTTPException(400, "File size must be between 0 bytes and 5 TiB")
        if not overwrite and self._exists(key):
            raise HTTPException(409, f"{path} already exists")
        metadata = {"uploaded-by": user}
        if size == 0:
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=b"", Metadata=metadata)
            return {"key": key, "upload_id": None, "part_size": 0, "parts": 0}
        upload = self.s3.create_multipart_upload(Bucket=self.bucket, Key=key, Metadata=metadata)
        psize = part_size(size)
        return {"key": key, "upload_id": upload["UploadId"], "part_size": psize, "parts": math.ceil(size / psize)}

    def _upload_key(self, key: str) -> str:
        root = ROOTS["uploads"].prefix
        if not key.startswith(root):
            raise HTTPException(403, "Uploads go under uploads/")
        return root + clean_path(key[len(root) :])

    def part_urls(self, key: str, upload_id: str, part_numbers: list[int]) -> dict:
        key = self._upload_key(key)
        if not part_numbers or len(part_numbers) > 100 or any(n < 1 or n > MAX_PARTS for n in part_numbers):
            raise HTTPException(400, "Ask for 1 to 100 part numbers between 1 and 10000")
        urls = {
            str(n): self.s3.generate_presigned_url(
                "upload_part",
                Params={"Bucket": self.bucket, "Key": key, "UploadId": upload_id, "PartNumber": n},
                ExpiresIn=URL_SECONDS,
            )
            for n in part_numbers
        }
        return {"urls": urls}

    def complete(self, key: str, upload_id: str, parts: list[dict]) -> dict:
        key = self._upload_key(key)
        ordered = sorted(parts, key=lambda p: p["part_number"])
        ordered = [{"PartNumber": p["part_number"], "ETag": p["etag"]} for p in ordered]
        self.s3.complete_multipart_upload(
            Bucket=self.bucket, Key=key, UploadId=upload_id, MultipartUpload={"Parts": ordered}
        )
        return {"key": key}

    def abort(self, key: str, upload_id: str) -> dict:
        key = self._upload_key(key)
        self.s3.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
        return {"aborted": key}


def _iso(d: datetime) -> str:
    return d.isoformat()
