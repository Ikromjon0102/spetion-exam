"""File storage for raw exam uploads. See CLAUDE.md "File storage".

Two backends, picked by settings.storage_backend:
  - "s3" (default): MinIO locally / real S3 in prod — the decided stack.
  - "local": plain disk under settings.local_storage_dir, for developing
    without Docker/MinIO running. Never the default; opt in via .env.
"""

import uuid
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4", connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}),
        )
    return _s3_client


def ensure_bucket() -> None:
    if settings.storage_backend == "local":
        Path(settings.local_storage_dir).mkdir(parents=True, exist_ok=True)
        return
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_exam_file(file_bytes: bytes, original_filename: str) -> str:
    """Uploads raw exam file bytes, returns the storage key."""
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    key = f"exam-uploads/{uuid.uuid4().hex}.{ext}"

    if settings.storage_backend == "local":
        path = Path(settings.local_storage_dir) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)
        return key

    get_s3_client().put_object(Bucket=settings.s3_bucket, Key=key, Body=file_bytes)
    return key


def download_exam_file(storage_key: str) -> bytes:
    if settings.storage_backend == "local":
        return (Path(settings.local_storage_dir) / storage_key).read_bytes()

    obj = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=storage_key)
    return obj["Body"].read()
