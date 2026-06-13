"""MinIO/S3 yükleme ve presigned URL (Spec Bölüm 7.2 adım 4, Bölüm 16 adım 40).

NOT: Testlerde bu fonksiyonlar mock'lanır (conftest); CI gerçek MinIO gerektirmez.
"""
from __future__ import annotations

import boto3

from app.core.config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )


def ensure_bucket() -> None:
    client = _client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET)
    except Exception:  # noqa: BLE001
        client.create_bucket(Bucket=settings.S3_BUCKET)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Baytları MinIO'ya yükler ve nesne anahtarını (s3_path) döndürür."""
    ensure_bucket()
    _client().put_object(Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=content_type)
    return key


def generate_presigned_url(key: str, expires_seconds: int | None = None) -> str:
    """Nesne için süreli (varsayılan 24 saat) indirme URL'i üretir."""
    expires = expires_seconds or settings.PRESIGNED_URL_EXPIRE_HOURS * 3600
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": settings.S3_BUCKET, "Key": key}, ExpiresIn=expires
    )
