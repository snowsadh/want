import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from apps.api.app.contracts import GarmentAnalysis, LookAnalysis
from apps.api.app.look_builder import LookBuilder, _require_public_https_url, normalize_inventory
from apps.api.app.openai_discovery import (
    InventoryTrace,
    ItemTrace,
    ShoppingProduct,
    ShoppingResult,
)


def garment(
    item_id: str,
    category: str = "top",
    box: list[int] | None = None,
    body_slot: str | None = None,
) -> GarmentAnalysis:
    return GarmentAnalysis(
        item_id=item_id,
        body_slot=body_slot or ("shoes" if "shoe" in category else "upper_body"),
        category=category,
        box_2d=box or [100, 100, 600, 900],
        visibility="clear",
        visible_fraction=1,
        colors=["black"],
        silhouette="fitted",
        material_appearance="matte",
        pattern="solid",
        print_or_graphic="none",
        details=[],
    )


def test_normalization_merges_pairs_and_removes_only_strong_duplicates() -> None:
    normalized = normalize_inventory(
        LookAnalysis(
            garments=[
                garment("left_shoe", "low-top sneakers", [700, 100, 950, 400], "shoes"),
                garment("right_shoe", "low-top sneakers", [700, 600, 950, 900], "shoes"),
                garment("top_1"),
                garment("top_duplicate", box=[102, 102, 598, 898]),
                garment("layer", category="cardigan", box=[50, 50, 650, 950]),
            ]
        )
    )

    assert [item.item_id for item in normalized.garments] == [
        "top_1",
        "layer",
        "left_shoe",
    ]
    assert normalized.garments[-1].box_2d == [700, 100, 950, 900]


def test_builder_uses_raw_image_fallback_and_retries_failed_rows(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jpg"
    Image.new("RGB", (200, 300), "black").save(capture)
    analysis = LookAnalysis(garments=[garment("upper_1"), garment("bag_1", "bag")])

    class Discovery:
        async def inventory(self, _path: Path) -> InventoryTrace:
            return InventoryTrace(
                prompt_version="test",
                latency_seconds=1,
                response_id="inventory-1",
                usage={},
                analysis=analysis,
            )

        async def shop(self, _path: Path, items, exclusions=None) -> list[ItemTrace]:
            if exclusions is not None:
                assert exclusions == {"bag_1": []}
                assert [item[0].item_id for item in items] == ["bag_1"]
                return [
                    ItemTrace(
                        item_id="bag_1",
                        latency_seconds=1,
                        response_id="shop-retry-1",
                        web_search_calls=1,
                        usage={},
                        result=ShoppingResult(
                            item_id="bag_1",
                            search_queries=["black bag"],
                            products=[
                                ShoppingProduct(
                                    match_kind="similar",
                                    title="Black bag",
                                    retailer="Bag Store",
                                    product_url="https://example.com/bag",
                                    image_url="https://example.com/bag.jpg",
                                    listed_price=30,
                                    listed_currency="USD",
                                )
                            ],
                            give_up_reason=None,
                        ),
                        error=None,
                    )
                ]
            assert len(items) == 2
            return [
                ItemTrace(
                    item_id="upper_1",
                    latency_seconds=1,
                    response_id="shop-1",
                    web_search_calls=2,
                    usage={},
                    result=ShoppingResult(
                        item_id="upper_1",
                        search_queries=["black top"],
                        products=[
                            ShoppingProduct(
                                match_kind="similar",
                                title="Black top",
                                retailer="Store",
                                product_url="https://example.com/top",
                                image_url="https://example.com/top.jpg",
                                listed_price=20,
                                listed_currency="USD",
                            ),
                            ShoppingProduct(
                                match_kind="similar",
                                title="Black top India",
                                retailer="Store India",
                                product_url="https://example.com/top-in",
                                image_url="https://example.com/top-in.jpg",
                                listed_price=1699,
                                listed_currency="INR",
                            ),
                        ],
                        give_up_reason=None,
                    ),
                    image_alternates={
                        "https://example.com/top": ["https://example.com/top-alt.jpg"]
                    },
                    error=None,
                ),
                ItemTrace(
                    item_id="bag_1",
                    latency_seconds=1,
                    response_id=None,
                    web_search_calls=0,
                    usage={},
                    result=None,
                    error="search failed",
                ),
            ]

    product_image = BytesIO()
    Image.new("RGB", (320, 480), "white").save(product_image, "JPEG")

    async def fetch_image(url: str) -> bytes:
        if url.endswith("/top.jpg"):
            raise OSError("retailer blocked the image")
        return product_image.getvalue()

    result = asyncio.run(
        LookBuilder(Discovery(), tmp_path / "media", fetch_image).build(  # type: ignore[arg-type]
            capture, "test-look"
        )
    ).result

    assert len(result.items) == 2
    assert len(result.items[0].products) == 2
    assert result.items[0].products[0].price_minor == 2000
    assert result.items[0].products[0].currency == "USD"
    assert result.items[0].products[1].price_minor == 169900
    assert result.items[0].products[1].currency == "INR"
    assert all(product.image_ref for product in result.items[0].products)
    assert result.items[1].products[0].title == "Black bag"
    assert all(
        (tmp_path / "media" / row.crop_ref.removeprefix("/media/")).is_file()
        for row in result.items
    )


def test_product_image_download_rejects_private_networks() -> None:
    with pytest.raises(ValueError, match="public address"):
        asyncio.run(_require_public_https_url("https://127.0.0.1/product.jpg"))


def test_product_image_is_normalized_for_youcam(tmp_path: Path) -> None:
    payload = BytesIO()
    Image.new("RGBA", (5000, 1000), (0, 0, 0, 0)).save(payload, "PNG")

    async def fetch_image(_url: str) -> bytes:
        return payload.getvalue()

    builder = LookBuilder(object(), tmp_path, fetch_image)  # type: ignore[arg-type]
    ref = asyncio.run(
        builder._cache_product_image(
            "https://example.com/product.png", "look", "item", 1, fetch_image
        )
    )

    assert ref == "/media/looks/look/products/item-1.jpg"
    with Image.open(tmp_path / "looks/look/products/item-1.jpg") as image:
        assert image.mode == "RGB"
        assert image.size == (4096, 819)
        assert image.getpixel((0, 0)) == (255, 255, 255)
