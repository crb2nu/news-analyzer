from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from minio.error import S3Error

from minio import Minio

from .config import Settings


def _build_minio_client(settings: Settings) -> Optional[Minio]:
    ep = settings.minio_endpoint.strip()
    default_secure = None
    if ep.startswith("http://"):
        ep = ep[len("http://"):]
        default_secure = False
    elif ep.startswith("https://"):
        ep = ep[len("https://"):]
        default_secure = True

    if ":" in ep:
        host, port_str = ep.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            host, port = ep, None
    else:
        host, port = ep, None

    is_k8s_svc = host.endswith(".svc") or host.endswith(".svc.cluster.local")
    is_local = host.startswith("localhost") or host.endswith(".lan")
    secure = (default_secure if default_secure is not None else not (is_k8s_svc or is_local))
    if port is None:
        port = 80 if not secure else 9000

    endpoint = f"{host}:{port}"
    client = Minio(
        endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
    )
    # Ensure bucket exists
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    return client


class MinioHelper:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self.client = _build_minio_client(self.settings)

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        if not self.client:
            return False
        from io import BytesIO
        self.client.put_object(
            bucket_name=self.settings.minio_bucket,
            object_name=key,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return True

    def put_text(self, key: str, text: str, encoding: str = "utf-8") -> bool:
        return self.put_bytes(key, text.encode(encoding), content_type="text/html; charset=utf-8")

    def get_text(self, key: str, encoding: str = "utf-8") -> Optional[str]:
        if not self.client:
            return None
        try:
            response = self.client.get_object(
                bucket_name=self.settings.minio_bucket,
                object_name=key,
            )
            try:
                data = response.read()
            finally:
                response.close()
                response.release_conn()
            return data.decode(encoding)
        except S3Error:
            return None
        except Exception:
            return None

    def delete_object(self, key: str) -> bool:
        if not self.client:
            return False
        try:
            self.client.remove_object(
                bucket_name=self.settings.minio_bucket,
                object_name=key,
            )
            return True
        except S3Error:
            return False

    @staticmethod
    def ts() -> str:
        return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
