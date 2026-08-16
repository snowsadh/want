from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from openai import APIError, AsyncOpenAI
from pydantic import Field, field_validator, model_validator

from apps.api.app.contracts import GarmentAnalysis, LookAnalysis, MatchKind, StrictModel
from apps.api.app.openai_prompts import (
    INVENTORY_PROMPT,
    INVENTORY_PROMPT_VERSION,
    SHOPPING_PROMPT,
    SHOPPING_PROMPT_VERSION,
)


class ShoppingProduct(StrictModel):
    match_kind: MatchKind
    title: str
    retailer: str
    product_url: str
    image_url: str
    listed_price: float | None = Field(ge=0)
    listed_currency: str | None

    @field_validator("product_url", "image_url")
    @classmethod
    def public_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("product and image URLs must use http or https")
        return value

    @model_validator(mode="after")
    def coherent_price(self) -> ShoppingProduct:
        if (self.listed_price is None) != (self.listed_currency is None):
            raise ValueError("listed price and currency must both be present or both be null")
        if self.listed_currency is not None:
            currency = self.listed_currency.strip().upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("listed currency must be a three-letter code")
            self.listed_currency = currency
        return self


class ShoppingResult(StrictModel):
    item_id: str
    search_queries: list[str]
    products: list[ShoppingProduct] = Field(max_length=3)
    give_up_reason: str | None

    @model_validator(mode="after")
    def coherent_result(self) -> ShoppingResult:
        urls = [str(product.product_url) for product in self.products]
        if len(urls) != len(set(urls)):
            raise ValueError("shopping products must be distinct")
        if not self.products and not self.give_up_reason:
            raise ValueError("an empty result requires a give-up reason")
        return self


class InventoryTrace(StrictModel):
    prompt_version: str
    latency_seconds: float
    response_id: str
    usage: dict[str, int]
    analysis: LookAnalysis


class ItemTrace(StrictModel):
    item_id: str
    latency_seconds: float
    response_id: str | None
    web_search_calls: int
    usage: dict[str, int]
    result: ShoppingResult | None
    error: str | None


@dataclass
class OpenAIDiscovery:
    api_key: str
    model: str = "gpt-5.6-terra"
    reasoning_effort: str = "medium"
    concurrency: int = 8
    search_context_size: Literal["low", "medium", "high"] = "low"
    service_tier: Literal["default", "fast"] = "default"

    def __post_init__(self) -> None:
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def inventory(self, image_path: Path) -> InventoryTrace:
        started = time.perf_counter()
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = await self.client.responses.parse(
                    model=self.model,
                    reasoning={"effort": self.reasoning_effort},
                    text={"verbosity": "low"},
                    store=False,
                    service_tier=self.service_tier,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": INVENTORY_PROMPT},
                                _input_image(image_path),
                            ],
                        }
                    ],
                    text_format=LookAnalysis,
                )
                if response.output_parsed is None:
                    raise ValueError("OpenAI returned no parsed inventory")
                return InventoryTrace(
                    prompt_version=INVENTORY_PROMPT_VERSION,
                    latency_seconds=time.perf_counter() - started,
                    response_id=response.id,
                    usage=_usage_dict(response.usage),
                    analysis=response.output_parsed,
                )
            except (APIError, TypeError, ValueError) as error:
                last_error = error
        raise ValueError(f"OpenAI inventory failed: {last_error}") from last_error

    async def shop(
        self,
        image_path: Path,
        items: list[tuple[GarmentAnalysis, Path]],
    ) -> list[ItemTrace]:
        semaphore = asyncio.Semaphore(max(1, self.concurrency))

        async def bounded(item: tuple[GarmentAnalysis, Path]) -> ItemTrace:
            async with semaphore:
                return await self._shop_item(image_path, *item)

        return list(await asyncio.gather(*(bounded(item) for item in items)))

    async def _shop_item(
        self,
        image_path: Path,
        garment: GarmentAnalysis,
        crop_path: Path,
    ) -> ItemTrace:
        started = time.perf_counter()
        try:
            response = await self.client.responses.parse(
                model=self.model,
                reasoning={"effort": self.reasoning_effort},
                text={"verbosity": "low"},
                store=False,
                service_tier=self.service_tier,
                max_tool_calls=3,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": self.search_context_size,
                        "search_content_types": ["image", "text"],
                        "image_settings": {"max_results": 10, "caption": True},
                    }
                ],  # type: ignore[list-item] -- image-search fields lead the installed SDK types.
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": SHOPPING_PROMPT},
                            {
                                "type": "input_text",
                                "text": "TARGET ITEM:\n"
                                + json.dumps(garment.model_dump(mode="json")),
                            },
                            {"type": "input_text", "text": "TARGET CROP:"},
                            _input_image(crop_path),
                            {"type": "input_text", "text": "FULL REFERENCE:"},
                            _input_image(image_path),
                        ],
                    }
                ],
                text_format=ShoppingResult,
            )
            result = response.output_parsed
            if result is None:
                raise ValueError("OpenAI returned no parsed shopping result")
            if result.item_id != garment.item_id:
                raise ValueError(
                    f"OpenAI returned item {result.item_id!r} for {garment.item_id!r}"
                )
            return ItemTrace(
                item_id=garment.item_id,
                latency_seconds=time.perf_counter() - started,
                response_id=response.id,
                web_search_calls=_count_web_search_calls(response.output),
                usage=_usage_dict(response.usage),
                result=result,
                error=None,
            )
        except (APIError, TypeError, ValueError) as error:
            return ItemTrace(
                item_id=garment.item_id,
                latency_seconds=time.perf_counter() - started,
                response_id=None,
                web_search_calls=0,
                usage={},
                result=None,
                error=f"{type(error).__name__}: {str(error)[:500]}",
            )


def _input_image(path: Path) -> dict[str, str]:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{mime_type};base64,{encoded}",
        "detail": "original",
    }


def _count_web_search_calls(output: list[Any]) -> int:
    return sum(getattr(item, "type", None) == "web_search_call" for item in output)


def _usage_dict(usage: Any) -> dict[str, int]:
    if usage is None:
        return {}
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def trace_summary(inventory: InventoryTrace, items: list[ItemTrace]) -> dict[str, Any]:
    return {
        "inventory_prompt": inventory.prompt_version,
        "shopping_prompt": SHOPPING_PROMPT_VERSION,
        "inventory_seconds": round(inventory.latency_seconds, 3),
        "shopping_seconds": round(max((item.latency_seconds for item in items), default=0), 3),
        "web_search_calls": sum(item.web_search_calls for item in items),
        "total_tokens": inventory.usage.get("total_tokens", 0)
        + sum(item.usage.get("total_tokens", 0) for item in items),
        "item_errors": {item.item_id: item.error for item in items if item.error},
    }
