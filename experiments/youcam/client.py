from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

GarmentCategory = Literal["upper_body", "lower_body", "full_body"]


@dataclass(frozen=True)
class TryOnResult:
    task_id: str
    latency_seconds: float
    raw: dict[str, Any]
    image_bytes: bytes


class YouCamClient:
    BASE_URL = "https://yce-api-01.makeupar.com"

    def __init__(self, api_key: str, timeout: float = 45.0) -> None:
        self._http = httpx.Client(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            follow_redirects=True,
        )

    def upload(self, image_path: Path) -> str:
        content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        size = image_path.stat().st_size
        response = self._http.post(
            "/s2s/v2.0/file/cloth-v3",
            json={
                "files": [
                    {"content_type": content_type, "file_name": image_path.name, "file_size": size}
                ]
            },
        )
        response.raise_for_status()
        payload = response.json()
        self._raise_api_error(payload, "request upload")
        file_info = payload["data"]["files"][0]
        upload_request = file_info["requests"][0]
        with image_path.open("rb") as handle:
            upload = httpx.put(
                upload_request["url"],
                headers=upload_request.get("headers") or {"Content-Type": content_type},
                content=handle.read(),
                timeout=45.0,
            )
        upload.raise_for_status()
        return str(file_info["file_id"])

    def create_task(
        self,
        src_file_id: str,
        category: GarmentCategory,
        *,
        ref_file_id: str | None = None,
        ref_file_url: str | None = None,
    ) -> str:
        if bool(ref_file_id) == bool(ref_file_url):
            raise ValueError("Provide exactly one of ref_file_id or ref_file_url")
        body: dict[str, str] = {"src_file_id": src_file_id, "garment_category": category}
        if ref_file_id:
            body["ref_file_id"] = ref_file_id
        if ref_file_url:
            body["ref_file_url"] = ref_file_url
        response = self._http.post("/s2s/v2.0/task/cloth-v3", json=body)
        response.raise_for_status()
        payload = response.json()
        self._raise_api_error(payload, "create task")
        return str(payload["data"]["task_id"])

    def wait(self, task_id: str, timeout_seconds: float = 180.0) -> TryOnResult:
        started = time.perf_counter()
        while time.perf_counter() - started < timeout_seconds:
            response = self._http.get(f"/s2s/v2.0/task/cloth-v3/{task_id}")
            response.raise_for_status()
            payload = response.json()
            self._raise_api_error(payload, "poll task")
            data = payload.get("data") or {}
            status = str(data.get("task_status") or "").lower()
            if status == "success":
                result_url = (data.get("results") or {}).get("url")
                if not result_url:
                    raise RuntimeError("YouCam success response did not include a result URL")
                result_response = httpx.get(result_url, timeout=45.0, follow_redirects=True)
                result_response.raise_for_status()
                return TryOnResult(
                    task_id=task_id,
                    latency_seconds=time.perf_counter() - started,
                    raw=payload,
                    image_bytes=result_response.content,
                )
            if status in {"error", "failed", "failure"} or data.get("error"):
                raise RuntimeError(f"YouCam task failed: {data.get('error') or status}")
            time.sleep(2.0)
        raise TimeoutError(f"YouCam task {task_id} exceeded {timeout_seconds:.0f}s")

    def render(
        self,
        source: Path,
        category: GarmentCategory,
        *,
        reference: Path | None = None,
        reference_url: str | None = None,
    ) -> TryOnResult:
        if bool(reference) == bool(reference_url):
            raise ValueError("Provide exactly one reference path or URL")
        started = time.perf_counter()
        source_id = self.upload(source)
        ref_id = self.upload(reference) if reference else None
        task_id = self.create_task(
            source_id, category, ref_file_id=ref_id, ref_file_url=reference_url
        )
        result = self.wait(task_id)
        return TryOnResult(
            task_id=result.task_id,
            latency_seconds=time.perf_counter() - started,
            raw=result.raw,
            image_bytes=result.image_bytes,
        )

    @staticmethod
    def _raise_api_error(payload: dict[str, Any], operation: str) -> None:
        if payload.get("status") not in (None, 200):
            detail = payload.get("error") or payload.get("message") or "unknown error"
            raise RuntimeError(f"YouCam {operation} failed: {detail}")
