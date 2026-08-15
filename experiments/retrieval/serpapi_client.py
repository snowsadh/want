from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from experiments.common.models import Product

SECOND_HAND_RE = re.compile(
    r"\b(used|pre[- ]?owned|second[- ]?hand|thrifted|refurbished)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class SearchResult:
    products: list[Product]
    latency_seconds: float
    raw: dict[str, Any]


class SerpApiClient:
    def __init__(self, api_key: str, timeout: float = 45.0) -> None:
        self.api_key = api_key
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)

    def upload_image(self, image_path: Path) -> str:
        if image_path.stat().st_size > 500_000:
            raise ValueError("SerpApi Image API documents a 500 KB maximum")
        with image_path.open("rb") as handle:
            response = self._http.post(
                "https://serpapi.com/image",
                data={"api_key": self.api_key},
                files={"image": (image_path.name, handle, "image/jpeg")},
            )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("image_id"):
            raise RuntimeError(f"SerpApi upload failed: {payload.get('error', 'missing image_id')}")
        return str(payload["image_id"])

    def lens_products(
        self, image_path: Path, country: str, query: str | None = None
    ) -> SearchResult:
        started = time.perf_counter()
        image_id = self.upload_image(image_path)
        params = {
            "engine": "google_lens",
            "image_id": image_id,
            "type": "products",
            "country": country,
            "hl": "en",
            "safe": "active",
            "api_key": self.api_key,
        }
        if query:
            params["q"] = query
        response = self._http.get("https://serpapi.com/search.json", params=params)
        response.raise_for_status()
        raw = response.json()
        if raw.get("error"):
            raise RuntimeError(f"SerpApi Lens failed: {raw['error']}")
        products = list(self._normalize(raw, country))
        return SearchResult(products, time.perf_counter() - started, raw)

    def shopping_products(self, query: str, country: str) -> SearchResult:
        started = time.perf_counter()
        location = {
            "us": "New York, New York, United States",
            "in": "Bengaluru, Karnataka, India",
        }[country]
        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": country,
            "hl": "en",
            "location": location,
            "api_key": self.api_key,
        }
        if country == "in":
            params["google_domain"] = "google.co.in"
        response = self._http.get("https://serpapi.com/search.json", params=params)
        response.raise_for_status()
        raw = response.json()
        if raw.get("error"):
            raise RuntimeError(f"SerpApi Shopping failed: {raw['error']}")
        products = list(self._normalize(raw, country))
        return SearchResult(products, time.perf_counter() - started, raw)

    def _normalize(self, raw: dict[str, Any], country: str) -> Iterable[Product]:
        currency = "USD" if country == "us" else "INR"
        rows: list[dict[str, Any]] = []
        for key in ("shopping_results", "visual_matches", "products"):
            value = raw.get(key)
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
        seen: set[str] = set()
        for row in rows:
            title = str(row.get("title") or "").strip()
            source = str(row.get("source") or "").strip()
            condition = str(row.get("second_hand_condition") or row.get("condition") or "new")
            link = str(row.get("product_link") or row.get("link") or "").strip()
            image = str(row.get("image") or row.get("thumbnail") or "").strip()
            price = row.get("extracted_price")
            if price is None:
                price = _parse_price(row.get("price"))
            if (
                not title
                or not link.startswith("http")
                or not image.startswith("http")
                or not isinstance(price, (int, float))
                or price <= 0
                or condition.lower() != "new"
                or SECOND_HAND_RE.search(f"{title} {condition}")
            ):
                continue
            identity = str(row.get("product_id") or link)
            if identity in seen:
                continue
            seen.add(identity)
            yield Product(
                provider_id=hashlib.sha256(identity.encode()).hexdigest()[:20],
                title=title,
                source=source or "unknown",
                price=float(price),
                currency=str(row.get("currency") or currency),
                product_url=link,
                image_url=image,
                region=country,
                condition="new",
                raw_position=row.get("position") if isinstance(row.get("position"), int) else None,
            )


def _parse_price(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(?:\d[\d,]*)(?:\.\d+)?", value)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None
