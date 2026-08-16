import asyncio
from pathlib import Path

from PIL import Image

from apps.api.app.contracts import GarmentAnalysis, LookAnalysis
from apps.api.app.look_builder import LookBuilder, normalize_inventory
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


def test_builder_keeps_other_items_when_one_shopper_fails(tmp_path: Path) -> None:
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

        async def shop(self, _path: Path, items) -> list[ItemTrace]:
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

    result = asyncio.run(
        LookBuilder(Discovery(), tmp_path / "media").build(  # type: ignore[arg-type]
            capture, "test-look"
        )
    ).result

    assert len(result.items) == 2
    assert result.items[0].products[0].price_minor == 2000
    assert result.items[0].products[0].currency == "USD"
    assert result.items[0].products[1].price_minor == 169900
    assert result.items[0].products[1].currency == "INR"
    assert result.items[1].products == []
    assert result.items[1].give_up_reason == "search failed"
    assert all((tmp_path / "media" / row.crop_ref.removeprefix("/media/")).is_file() for row in result.items)
