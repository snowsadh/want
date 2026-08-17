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
        reference_refs: dict[str, str] | None = None,
    ) -> TryOnJob:
        steps = self._steps(look, selections or {}, reference_refs or {})
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
            rendered_item_ids: list[str] = []
            unavailable_item_ids: list[str] = []
            for item_id, slot, reference_url in steps:
                self._update(job_id, stage=f"applying_{slot.value}")
                try:
                    if reference_url.startswith("/media/"):
                        result = self.client.render(
                            source,
                            slot.value,
                            reference=self._media_path(reference_url),
                        )
                    else:
                        result = self.client.render(
                            source,
                            slot.value,
                            reference_url=reference_url,
                        )
                except RuntimeError as error:
                    if "error_download_image" not in str(error):
                        raise
                    unavailable_item_ids.append(item_id)
                    continue
                destination = job_dir / f"stage-{len(rendered_item_ids) + 1}.jpg"
                destination.write_bytes(result.image_bytes)
                source = destination
                rendered_item_ids.append(item_id)
            if not rendered_item_ids:
                raise RuntimeError(
                    "YouCam could not download any selected retailer image. "
                    "Choose another product option and try again."
                )
            result_ref = f"/media/{source.relative_to(self.media_dir).as_posix()}"
            unavailable_count = len(unavailable_item_ids)
            warning = (
                f"{unavailable_count} selected piece"
                f"{'s' if unavailable_count != 1 else ''} stayed out of the preview because "
                f"{'their' if unavailable_count != 1 else 'its'} retailer image was unavailable "
                "to YouCam."
                if unavailable_count
                else None
            )
            self._update(
                job_id,
                status=TryOnStatus.SUCCESS,
                stage="complete",
                result_ref=result_ref,
                error=warning,
                rendered_garment_item_ids=rendered_item_ids,
            )
        except (
            httpx.HTTPError,
            OSError,
            RuntimeError,
            TimeoutError,
            ValueError,
            KeyError,
        ) as error:
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
        reference_refs: dict[str, str] | None = None,
    ) -> list[tuple[str, BodySlot, str]]:
        selections = selections or {}
        reference_refs = reference_refs or {}
        rows = {item.item_id: item for item in look.result.items}
        unknown = set(selections) - set(rows)
        if unknown:
            raise ValueError(f"Unknown selected item: {min(unknown)}")

        garments = {garment.item_id: garment for garment in look.result.analysis.garments}
        references: dict[BodySlot, list[tuple[str, str, GarmentAnalysis]]] = {}
        for item_id, row in rows.items():
            garment = garments[item_id]
            if not _is_renderable(garment) or not row.products:
                continue
            selected = selections.get(item_id, row.selected_index)
            if not 0 <= selected < len(row.products):
                raise ValueError(f"Selected rank is out of range for {item_id}")
            references.setdefault(garment.body_slot, []).append(
                (
                    item_id,
                    reference_refs.get(item_id)
                    or row.products[selected].image_ref
                    or str(row.products[selected].image_url),
                    garment,
                )
            )

        chosen = {
            slot: max(items, key=lambda item: _render_priority(item[2]))
            for slot, items in references.items()
        }

        if BodySlot.FULL_BODY in chosen:
            item_id, reference, _garment = chosen[BodySlot.FULL_BODY]
            steps = [(item_id, BodySlot.FULL_BODY, reference)]
            if BodySlot.SHOES in chosen:
                shoe_id, shoe_reference, _garment = chosen[BodySlot.SHOES]
                steps.append((shoe_id, BodySlot.SHOES, shoe_reference))
            return steps
        return [
            (chosen[slot][0], slot, chosen[slot][1])
            for slot in (BodySlot.UPPER_BODY, BodySlot.LOWER_BODY, BodySlot.SHOES)
            if slot in chosen
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
    if any(
        word in category
        for word in ("sock", "stocking", "tights", "hosiery", "leg warmer", "underlayer")
    ):
        return False
    return garment.body_slot in {
        BodySlot.UPPER_BODY,
        BodySlot.LOWER_BODY,
        BodySlot.FULL_BODY,
        BodySlot.SHOES,
    }


def _render_priority(garment: GarmentAnalysis) -> tuple[int, float, int]:
    """Prefer an outer visible layer when Clothes V3 can render only one per slot."""
    description = " ".join((garment.category, garment.silhouette, *garment.details)).casefold()
    outer_layer = int(
        any(
            word in description
            for word in ("coat", "jacket", "blazer", "cardigan", "overshirt", "outerwear", "vest")
        )
    )
    ymin, xmin, ymax, xmax = garment.box_2d
    return outer_layer, garment.visible_fraction, (ymax - ymin) * (xmax - xmin)
