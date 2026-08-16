from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from apps.api.app.contracts import (
    BodySlot,
    GarmentAnalysis,
    LookBuildResponse,
    TryOnJob,
    TryOnStatus,
)
from apps.api.app.youcam import YouCamClient


class TryOnManager:
    def __init__(self, client: YouCamClient, media_dir: Path) -> None:
        self.client = client
        self.media_dir = media_dir
        self._jobs: dict[str, TryOnJob] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="want-try-on")

    def submit(
        self,
        look: LookBuildResponse,
        profile_ref: str,
        selections: dict[str, int] | None = None,
    ) -> TryOnJob:
        steps = self._steps(look, selections or {})
        if not steps:
            raise ValueError("This look has no matched apparel that Clothes V3 can render")
        job = TryOnJob(
            id=str(uuid4()),
            look_id=look.look_id,
            status=TryOnStatus.QUEUED,
            stage="queued",
        )
        with self._lock:
            self._jobs[job.id] = job
        self._pool.submit(self._run, job.id, look.look_id, profile_ref, steps)
        return job

    def get(self, job_id: str) -> TryOnJob:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise LookupError(job_id)
        return job

    def _run(
        self,
        job_id: str,
        look_id: str,
        profile_ref: str,
        steps: list[tuple[str, BodySlot, str]],
    ) -> None:
        try:
            self._update(job_id, status=TryOnStatus.RUNNING, stage="preparing")
            source = self._media_path(profile_ref)
            job_dir = self.media_dir / "looks" / look_id / "try-on" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            rendered_item_ids = []
            for index, (item_id, slot, reference_url) in enumerate(steps, start=1):
                self._update(job_id, stage=f"applying_{slot.value}")
                result = self.client.render(
                    source,
                    slot.value,
                    reference_url=reference_url,
                )
                destination = job_dir / f"stage-{index}.jpg"
                destination.write_bytes(result.image_bytes)
                source = destination
                rendered_item_ids.append(item_id)
            result_ref = f"/media/{source.relative_to(self.media_dir).as_posix()}"
            self._update(
                job_id,
                status=TryOnStatus.SUCCESS,
                stage="complete",
                result_ref=result_ref,
                rendered_garment_item_ids=rendered_item_ids,
            )
        except (httpx.HTTPError, OSError, RuntimeError, TimeoutError, ValueError, KeyError) as error:
            self._update(
                job_id,
                status=TryOnStatus.FAILED,
                stage="failed",
                error=str(error)[:300],
            )

    def _steps(
        self,
        look: LookBuildResponse,
        selections: dict[str, int] | None = None,
    ) -> list[tuple[str, BodySlot, str]]:
        selections = selections or {}
        rows = {item.item_id: item for item in look.result.items}
        unknown = set(selections) - set(rows)
        if unknown:
            raise ValueError(f"Unknown selected item: {min(unknown)}")

        garments = {garment.item_id: garment for garment in look.result.analysis.garments}
        references: dict[BodySlot, list[tuple[str, str]]] = {}
        for item_id, row in rows.items():
            garment = garments[item_id]
            if not _is_renderable(garment) or not row.products:
                continue
            selected = selections.get(item_id, row.selected_index)
            if not 0 <= selected < len(row.products):
                raise ValueError(f"Selected rank is out of range for {item_id}")
            references.setdefault(garment.body_slot, []).append(
                (item_id, str(row.products[selected].image_url))
            )

        if any(len(items) > 1 for items in references.values()) or (
            BodySlot.FULL_BODY in references
            and (BodySlot.UPPER_BODY in references or BodySlot.LOWER_BODY in references)
        ):
            raise ValueError(
                "Layered clothing is not supported reliably; choose a single-layer look"
            )

        if BodySlot.FULL_BODY in references:
            item_id, reference = references[BodySlot.FULL_BODY][0]
            steps = [(item_id, BodySlot.FULL_BODY, reference)]
            if BodySlot.SHOES in references:
                shoe_id, shoe_reference = references[BodySlot.SHOES][0]
                steps.append((shoe_id, BodySlot.SHOES, shoe_reference))
            return steps
        return [
            (references[slot][0][0], slot, references[slot][0][1])
            for slot in (BodySlot.UPPER_BODY, BodySlot.LOWER_BODY, BodySlot.SHOES)
            if slot in references
        ]

    def _media_path(self, ref: str) -> Path:
        parsed = urlparse(ref)
        path = parsed.path if parsed.scheme else ref
        if not path.startswith("/media/"):
            raise ValueError("Local source references must use /media/")
        candidate = (self.media_dir / path.removeprefix("/media/")).resolve()
        root = self.media_dir.resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError("A local source image is missing")
        return candidate

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(update=changes)


def _is_tied_layer(garment: GarmentAnalysis) -> bool:
    description = " ".join((garment.silhouette, *garment.details)).casefold()
    return any(
        phrase in description
        for phrase in (
            "tied around waist",
            "tied around the waist",
            "tied at waist",
            "tied at the waist",
            "sleeves tied at front",
            "wrapped waist garment",
        )
    )


def _is_renderable(garment: GarmentAnalysis) -> bool:
    if garment.body_slot is BodySlot.ACCESSORY or _is_tied_layer(garment):
        return False
    category = garment.category.casefold().replace("-", " ")
    if any(word in category for word in ("sock", "leg warmer")):
        return False
    return garment.body_slot in {
        BodySlot.UPPER_BODY,
        BodySlot.LOWER_BODY,
        BodySlot.FULL_BODY,
        BodySlot.SHOES,
    }
