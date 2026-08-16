from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from apps.api.app.contracts import (
    BodySlot,
    GarmentAnalysis,
    ItemResult,
    LookAnalysis,
    LookResult,
    ProductMatch,
    Visibility,
)
from apps.api.app.openai_discovery import ItemTrace, OpenAIDiscovery, trace_summary

LOGGER = logging.getLogger(__name__)
PAIR_WORDS = ("sock", "leg warmer")


@dataclass(frozen=True)
class BuiltLook:
    result: LookResult


class LookBuilder:
    def __init__(
        self,
        discovery: OpenAIDiscovery,
        media_dir: Path,
    ) -> None:
        self.discovery = discovery
        self.media_dir = media_dir

    async def build(self, capture_path: Path, look_id: str) -> BuiltLook:
        started = time.perf_counter()
        inventory = await self.discovery.inventory(capture_path)
        analysis = normalize_inventory(inventory.analysis)
        crop_inputs = [
            (garment, *self._make_crop(capture_path, look_id, garment))
            for garment in analysis.garments
        ]
        traces = await self.discovery.shop(
            capture_path,
            [(garment, crop_path) for garment, _crop_ref, crop_path in crop_inputs],
        )
        trace_by_id = {trace.item_id: trace for trace in traces}
        rows = [
            self._item_result(garment, crop_ref, trace_by_id[garment.item_id])
            for garment, crop_ref, _crop_path in crop_inputs
        ]
        diagnostics = trace_summary(inventory, traces)
        LOGGER.info(
            "look %s openai=%s total_seconds=%.3f",
            look_id,
            diagnostics,
            time.perf_counter() - started,
        )
        return BuiltLook(result=LookResult(analysis=analysis, items=rows))

    def _item_result(
        self,
        garment: GarmentAnalysis,
        crop_ref: str,
        trace: ItemTrace,
    ) -> ItemResult:
        result = trace.result
        products = []
        if result is not None:
            for candidate in result.products:
                products.append(
                    ProductMatch(
                        match_kind=candidate.match_kind,
                        title=candidate.title,
                        retailer=candidate.retailer,
                        product_url=candidate.product_url,
                        image_url=candidate.image_url,
                        price_minor=round(candidate.listed_price * 100)
                        if candidate.listed_price is not None
                        else None,
                        currency=candidate.listed_currency,
                    )
                )
        reason = (
            result.give_up_reason
            if result is not None and not products
            else trace.error if not products else None
        )
        return ItemResult(
            item_id=garment.item_id,
            crop_ref=crop_ref,
            products=products,
            give_up_reason=reason or ("No credible match found" if not products else None),
        )

    def _make_crop(
        self, capture_path: Path, look_id: str, garment: GarmentAnalysis
    ) -> tuple[str, Path]:
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", garment.item_id)[:60] or "item"
        relative = Path("looks") / look_id / "garments" / f"{safe_id}.jpg"
        destination = self.media_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(capture_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            width, height = image.size
            ymin, xmin, ymax, xmax = garment.box_2d
            left = int(xmin * width / 1000)
            top = int(ymin * height / 1000)
            right = max(left + 1, int(xmax * width / 1000))
            bottom = max(top + 1, int(ymax * height / 1000))
            pad_x = int((right - left) * 0.04)
            pad_y = int((bottom - top) * 0.04)
            image.crop(
                (
                    max(0, left - pad_x),
                    max(0, top - pad_y),
                    min(width, right + pad_x),
                    min(height, bottom + pad_y),
                )
            ).save(destination, "JPEG", quality=92, optimize=True)
        return f"/media/{relative.as_posix()}", destination


def normalize_inventory(analysis: LookAnalysis) -> LookAnalysis:
    paired: list[GarmentAnalysis] = []
    groups: dict[tuple[object, ...], list[GarmentAnalysis]] = {}
    for item in analysis.garments:
        pair_kind = _pair_kind(item)
        if pair_kind is None:
            paired.append(item)
            continue
        key = (
            pair_kind,
            item.body_slot,
            tuple(value.casefold() for value in item.colors),
            item.pattern.casefold(),
            item.silhouette.casefold(),
        )
        groups.setdefault(key, []).append(item)
    for items in groups.values():
        paired.append(_merge_items(items) if len(items) > 1 else items[0])

    deduped: list[GarmentAnalysis] = []
    for item in paired:
        if any(_is_duplicate(item, existing) for existing in deduped):
            continue
        deduped.append(item)
    return LookAnalysis(garments=deduped)


def _pair_kind(item: GarmentAnalysis) -> str | None:
    if item.body_slot is BodySlot.SHOES:
        return "footwear"
    normalized = item.category.casefold().replace("-", " ")
    return next((word for word in PAIR_WORDS if word in normalized), None)


def _merge_items(items: list[GarmentAnalysis]) -> GarmentAnalysis:
    first = items[0]
    return first.model_copy(
        update={
            "box_2d": [
                min(item.box_2d[0] for item in items),
                min(item.box_2d[1] for item in items),
                max(item.box_2d[2] for item in items),
                max(item.box_2d[3] for item in items),
            ],
            "visibility": Visibility.CLEAR
            if any(item.visibility is Visibility.CLEAR for item in items)
            else first.visibility,
            "visible_fraction": min(1, sum(item.visible_fraction for item in items)),
            "details": list(dict.fromkeys(detail for item in items for detail in item.details)),
        }
    )


def _is_duplicate(left: GarmentAnalysis, right: GarmentAnalysis) -> bool:
    return (
        left.body_slot is right.body_slot
        and left.category.casefold() == right.category.casefold()
        and _box_iou(left.box_2d, right.box_2d) >= 0.8
        and tuple(value.casefold() for value in left.colors)
        == tuple(value.casefold() for value in right.colors)
        and left.pattern.casefold() == right.pattern.casefold()
        and left.silhouette.casefold() == right.silhouette.casefold()
    )


def _box_iou(left: list[int], right: list[int]) -> float:
    intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0, min(left[3], right[3]) - max(left[1], right[1])
    )
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    return intersection / (left_area + right_area - intersection)
