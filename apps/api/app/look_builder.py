from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

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
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
ImageFetcher = Callable[[str], Awaitable[bytes]]


@dataclass(frozen=True)
class BuiltLook:
    result: LookResult


class LookBuilder:
    def __init__(
        self,
        discovery: OpenAIDiscovery,
        media_dir: Path,
        image_fetcher: ImageFetcher | None = None,
    ) -> None:
        self.discovery = discovery
        self.media_dir = media_dir
        self.image_fetcher = image_fetcher

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
        if self.image_fetcher is None:
            async with httpx.AsyncClient(
                timeout=12,
                follow_redirects=False,
                headers={
                    "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/140 Safari/537.36",
                    "Accept": "image/webp,image/png,image/jpeg,image/*;q=0.8",
                },
            ) as client:
                rows, retries = await self._build_with_retry(
                    capture_path, crop_inputs, traces, look_id, client
                )
        else:
            rows, retries = await self._build_with_retry(capture_path, crop_inputs, traces, look_id)
        diagnostics = trace_summary(inventory, [*traces, *retries])
        LOGGER.info(
            "look %s openai=%s total_seconds=%.3f",
            look_id,
            diagnostics,
            time.perf_counter() - started,
        )
        return BuiltLook(result=LookResult(analysis=analysis, items=rows))

    async def _build_with_retry(
        self,
        capture_path: Path,
        crop_inputs: list[tuple[GarmentAnalysis, str, Path]],
        traces: list[ItemTrace],
        look_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[list[ItemResult], list[ItemTrace]]:
        trace_by_id = {trace.item_id: trace for trace in traces}
        rows = await self._build_rows(crop_inputs, trace_by_id, look_id, client)
        missing_ids = {row.item_id for row in rows if not row.products}
        if not missing_ids:
            return rows, []

        retry_inputs = [item for item in crop_inputs if item[0].item_id in missing_ids]
        exclusions = {item_id: _trace_urls(trace_by_id[item_id]) for item_id in missing_ids}
        retry_traces = await self.discovery.shop(
            capture_path,
            [(garment, crop_path) for garment, _crop_ref, crop_path in retry_inputs],
            exclusions,
        )
        retry_rows = await self._build_rows(
            retry_inputs,
            {trace.item_id: trace for trace in retry_traces},
            look_id,
            client,
        )
        replacements = {row.item_id: row for row in retry_rows}
        return [replacements.get(row.item_id, row) for row in rows], retry_traces

    async def _build_rows(
        self,
        crop_inputs: list[tuple[GarmentAnalysis, str, Path]],
        trace_by_id: dict[str, ItemTrace],
        look_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> list[ItemResult]:
        semaphore = asyncio.Semaphore(8)

        async def fetch(url: str) -> bytes:
            async with semaphore:
                if self.image_fetcher is not None:
                    return await self.image_fetcher(url)
                if client is None:
                    raise RuntimeError("Product image client is unavailable")
                return await _download_public_image(client, url)

        return list(
            await asyncio.gather(
                *(
                    self._item_result(
                        garment,
                        crop_ref,
                        trace_by_id[garment.item_id],
                        look_id,
                        fetch,
                    )
                    for garment, crop_ref, _crop_path in crop_inputs
                )
            )
        )

    async def _item_result(
        self,
        garment: GarmentAnalysis,
        crop_ref: str,
        trace: ItemTrace,
        look_id: str,
        fetch: ImageFetcher,
    ) -> ItemResult:
        result = trace.result
        products: list[ProductMatch] = []
        if result is not None:
            image_refs = await asyncio.gather(
                *(
                    self._cache_product_image_options(
                        [
                            str(candidate.image_url),
                            *trace.image_alternates.get(
                                _comparison_url(str(candidate.product_url)), []
                            ),
                        ],
                        look_id,
                        garment.item_id,
                        rank,
                        fetch,
                    )
                    for rank, candidate in enumerate(result.products, start=1)
                )
            )
            for candidate, image_ref in zip(result.products, image_refs, strict=True):
                if image_ref is None:
                    continue
                products.append(
                    ProductMatch(
                        match_kind=candidate.match_kind,
                        title=candidate.title,
                        retailer=candidate.retailer,
                        product_url=candidate.product_url,
                        image_url=candidate.image_url,
                        image_ref=image_ref,
                        price_minor=round(candidate.listed_price * 100)
                        if candidate.listed_price is not None
                        else None,
                        currency=candidate.listed_currency,
                    )
                )
        reason = None
        if not products:
            if result is not None and result.products:
                reason = "Retailer product images were unavailable"
            else:
                reason = result.give_up_reason if result is not None else trace.error
        return ItemResult(
            item_id=garment.item_id,
            crop_ref=crop_ref,
            products=products,
            give_up_reason=reason or ("No credible match found" if not products else None),
        )

    async def _cache_product_image_options(
        self,
        image_urls: list[str],
        look_id: str,
        item_id: str,
        rank: int,
        fetch: ImageFetcher,
    ) -> str | None:
        for image_url in dict.fromkeys(image_urls):
            ref = await self._cache_product_image(image_url, look_id, item_id, rank, fetch)
            if ref is not None:
                return ref
        return None

    async def _cache_product_image(
        self,
        image_url: str,
        look_id: str,
        item_id: str,
        rank: int,
        fetch: ImageFetcher,
    ) -> str | None:
        try:
            payload = await fetch(image_url)
            if len(payload) > MAX_PRODUCT_IMAGE_BYTES:
                raise ValueError("product image exceeds 10 MB")
            with Image.open(BytesIO(payload)) as source:
                image = ImageOps.exif_transpose(source)
                if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                    foreground = image.convert("RGBA")
                    background = Image.new("RGBA", foreground.size, "white")
                    background.alpha_composite(foreground)
                    image = background.convert("RGB")
                else:
                    image = image.convert("RGB")
            if min(image.size) < 64:
                raise ValueError("product image dimensions are unsupported")
            if max(image.size) > 4096:
                image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", item_id)[:60] or "item"
            relative = Path("looks") / look_id / "products" / f"{safe_id}-{rank}.jpg"
            destination = self.media_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, "JPEG", quality=92, optimize=True)
            return f"/media/{relative.as_posix()}"
        except (
            httpx.HTTPError,
            OSError,
            TimeoutError,
            UnidentifiedImageError,
            ValueError,
        ) as error:
            hostname = urlparse(image_url).hostname or "unknown host"
            LOGGER.warning("dropping unavailable product image host=%s error=%s", hostname, error)
            return None

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


async def _download_public_image(client: httpx.AsyncClient, url: str) -> bytes:
    current = url
    for _redirect in range(4):
        await _require_public_https_url(current)
        async with client.stream("GET", current) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("image redirect is missing a destination")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                payload.extend(chunk)
                if len(payload) > MAX_PRODUCT_IMAGE_BYTES:
                    raise ValueError("product image exceeds 10 MB")
            return bytes(payload)
    raise ValueError("product image redirected too many times")


async def _require_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("product images must use public HTTPS URLs")
    addresses = await asyncio.to_thread(
        socket.getaddrinfo,
        parsed.hostname,
        parsed.port or 443,
        type=socket.SOCK_STREAM,
    )
    if not addresses or any(
        not ipaddress.ip_address(address[4][0]).is_global for address in addresses
    ):
        raise ValueError("product image host does not resolve to a public address")


def _comparison_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


def _trace_urls(trace: ItemTrace) -> list[str]:
    if trace.result is None:
        return []
    return list(
        dict.fromkeys(
            url
            for product in trace.result.products
            for url in (
                str(product.product_url),
                str(product.image_url),
                *trace.image_alternates.get(_comparison_url(str(product.product_url)), []),
            )
        )
    )
