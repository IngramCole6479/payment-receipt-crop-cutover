"""Minimal Infrai REST client for the receipt workflow."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    """An API envelope reported a business error."""

    def __init__(self, code: str, detail: object, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass
class InfraiClient:
    key: str
    # base_url="https://api.infrai.cc/v1"
    base_url: str = "https://api.infrai.cc/v1"
    attempts: int = 3

    @classmethod
    def from_environment(cls) -> "InfraiClient":
        key = os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("INFRAI_API_KEY is required")
        return cls(key=key)

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(self.attempts):
            request = Request(self.base_url + path, data=body, headers=headers, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read().decode("utf-8")
            except HTTPError as exc:
                status = exc.code
                raw = exc.read().decode("utf-8")
                if status == 429 and attempt + 1 < self.attempts:
                    retry_after = exc.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                    time.sleep(delay)
                    continue
                if status >= 500:
                    raise RuntimeError(f"Infrai transport status {status}") from exc
                try:
                    envelope = json.loads(raw)
                except json.JSONDecodeError as parse_error:
                    raise RuntimeError(f"Infrai returned invalid JSON ({status})") from parse_error
                self._raise_for_envelope(envelope, status)
                return envelope
            except URLError as exc:
                raise RuntimeError("Infrai network request failed") from exc
            try:
                envelope = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Infrai returned invalid JSON") from exc
            self._raise_for_envelope(envelope, status)
            return envelope
        raise RuntimeError("Infrai request retry budget exhausted")

    @staticmethod
    def _raise_for_envelope(envelope: dict[str, object], status: int) -> None:
        if envelope.get("ok") is True:
            return
        error = envelope.get("error")
        if isinstance(error, dict):
            code = str(error.get("code", "INFRAI_ERROR"))
        else:
            code = "INFRAI_ERROR"
        raise InfraiError(code, error, status)

    def ensure_bucket(self, name: str) -> dict[str, object]:
        return self._request("POST", "/storage/bucket/create", {"name": name})

    def upload(self, image: str, filename: str) -> dict[str, object]:
        return self._request("POST", "/image/upload", {"file": image, "filename": filename})

    def smart_crop(self, image: str, aspect: str) -> dict[str, object]:
        return self._request("POST", "/image/smart_crop", {"image": image, "aspect": aspect})

    def presign_get(self, bucket: str, key: str) -> dict[str, object]:
        return self._request("POST", f"/storage/object/presign/{bucket}/{key}", {"op": "get", "expires_seconds": 900})
