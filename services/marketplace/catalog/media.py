"""Storing photographs.

Photographs live in object storage rather than in Postgres: binaries bloat the
database, its write-ahead log and every backup, and a store built for bytes
serves them far better. MinIO speaks the S3 API, so this same code works
against S3 or any other S3-compatible store by changing the endpoint.

What arrives from a browser is untrusted. Every upload is decoded and
re-encoded here, which does three things at once: it proves the bytes really
are an image rather than something with an image's first few bytes, it drops
EXIF (photographs carry GPS coordinates, and an artisan's home should not ship
with their listing), and it caps the dimensions so one upload cannot fill the
disk.
"""

from __future__ import annotations

import io
import json
import logging
import uuid
from dataclasses import dataclass

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from django.conf import settings
from PIL import Image, UnidentifiedImageError

log = logging.getLogger(__name__)

MAX_BYTES = 6 * 1024 * 1024
MAX_EDGE = 2000  # a listing photograph never needs to be larger
ACCEPTED = {"image/jpeg", "image/png", "image/webp"}


class UploadRejected(Exception):
    """The file cannot be stored, and the person who sent it should be told why."""


@dataclass(frozen=True)
class StoredImage:
    url: str
    key: str


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.MEDIA_ENDPOINT,
        aws_access_key_id=settings.MEDIA_ACCESS_KEY,
        aws_secret_access_key=settings.MEDIA_SECRET_KEY,
        # MinIO serves the bucket as a path rather than a subdomain, which also
        # keeps the URLs working behind a gateway.
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="us-east-1",
    )


def _ensure_bucket(client) -> None:
    """Create the bucket, readable by anyone, if it is not there yet.

    Product photographs are public — they are on a public storefront — so the
    read policy is anonymous and the credentials only ever guard writes.
    """
    bucket = settings.MEDIA_BUCKET
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in ("404", "NoSuchBucket"):
            raise

    client.create_bucket(Bucket=bucket)
    client.put_bucket_policy(
        Bucket=bucket,
        Policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket}/*"],
                    }
                ],
            }
        ),
    )
    log.info("created media bucket", extra={"bucket": bucket})


def _normalise(raw: bytes) -> tuple[bytes, str, str]:
    """Decode, flatten and re-encode. Returns (bytes, content type, extension)."""
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()  # cheap structural check before decoding for real
        image = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError) as error:
        raise UploadRejected("That file is not an image we can read.") from error

    has_alpha = image.mode in ("RGBA", "LA", "P")
    image = image.convert("RGBA" if has_alpha else "RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE))

    buffer = io.BytesIO()
    if has_alpha:
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), "image/png", "png"
    # Re-encoding drops every EXIF field with it, including the GPS block.
    image.save(buffer, format="JPEG", quality=85, optimize=True, progressive=True)
    return buffer.getvalue(), "image/jpeg", "jpg"


def store_image(raw: bytes, declared_type: str, prefix: str) -> StoredImage:
    if len(raw) > MAX_BYTES:
        raise UploadRejected(f"Images must be under {MAX_BYTES // (1024 * 1024)} MB.")
    if declared_type and declared_type.split(";")[0].strip().lower() not in ACCEPTED:
        raise UploadRejected("Upload a JPEG, PNG or WebP image.")

    body, content_type, extension = _normalise(raw)
    key = f"{prefix}/{uuid.uuid4().hex}.{extension}"

    client = _client()
    _ensure_bucket(client)
    client.put_object(
        Bucket=settings.MEDIA_BUCKET,
        Key=key,
        Body=body,
        ContentType=content_type,
        # Photographs never change once stored — a new one gets a new key — so
        # they can be cached for as long as a browser likes.
        CacheControl="public, max-age=31536000, immutable",
    )
    return StoredImage(url=f"{settings.MEDIA_PUBLIC_BASE.rstrip('/')}/{key}", key=key)


def delete_image(url: str) -> None:
    """Remove the object a stored URL points at. Never raises."""
    base = settings.MEDIA_PUBLIC_BASE.rstrip("/") + "/"
    if not url.startswith(base):
        return  # a seeded image hosted elsewhere; nothing of ours to delete
    try:
        _client().delete_object(Bucket=settings.MEDIA_BUCKET, Key=url[len(base) :])
    except ClientError as error:
        # The listing is already gone from the database; a leftover object is
        # tidiness, not correctness.
        log.warning("could not delete stored image", extra={"error": str(error)})
