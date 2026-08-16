import asyncio
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from pydantic import ValidationError

from apps.api.app.contracts import GarmentAnalysis, MatchKind
from apps.api.app.openai_discovery import OpenAIDiscovery, ShoppingProduct, ShoppingResult


def product(title: str = "Black fitted top") -> ShoppingProduct:
    return ShoppingProduct(
        match_kind=MatchKind.SIMILAR,
        title=title,
        retailer="Example",
        product_url=f"https://example.com/{title.replace(' ', '-').lower()}",
        image_url=f"https://example.com/{title.replace(' ', '-').lower()}.jpg",
        listed_price=20,
        listed_currency="usd",
    )


def test_shopping_result_accepts_zero_to_three_distinct_products() -> None:
    ShoppingResult(
        item_id="upper_1",
        search_queries=["black fitted top"],
        products=[],
        give_up_reason="No credible match",
    )
    ShoppingResult(
        item_id="upper_1",
        search_queries=["black fitted top"],
        products=[product("one"), product("two"), product("three")],
        give_up_reason=None,
    )
    try:
        ShoppingResult(
            item_id="upper_1",
            search_queries=[],
            products=[product("one"), product("two"), product("three"), product("four")],
            give_up_reason=None,
        )
    except ValidationError:
        return
    raise AssertionError("four shopping products should be rejected")


def test_price_and_currency_must_be_paired() -> None:
    try:
        ShoppingProduct(
            match_kind="similar",
            title="Top",
            retailer="Store",
            product_url="https://example.com/top",
            image_url="https://example.com/top.jpg",
            listed_price=20,
            listed_currency=None,
        )
    except ValidationError:
        return
    raise AssertionError("a price without currency should be rejected")


def test_item_request_uses_image_search_and_three_tool_call_cap(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    crop = tmp_path / "crop.jpg"
    Image.new("RGB", (20, 30), "black").save(image)
    Image.new("RGB", (10, 15), "black").save(crop)
    garment = GarmentAnalysis(
        item_id="upper_1",
        body_slot="upper_body",
        category="fitted top",
        box_2d=[100, 100, 700, 900],
        visibility="clear",
        visible_fraction=1,
        colors=["black"],
        silhouette="fitted",
        material_appearance="matte knit",
        pattern="solid",
        print_or_graphic="none",
        details=[],
    )
    parsed = ShoppingResult(
        item_id="upper_1",
        search_queries=["black fitted top"],
        products=[product()],
        give_up_reason=None,
    )

    class Responses:
        def __init__(self) -> None:
            self.kwargs = {}

        async def parse(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                id="response-1",
                output_parsed=parsed,
                output=[SimpleNamespace(type="web_search_call")],
                usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
            )

    responses = Responses()
    discovery = OpenAIDiscovery("test-key")
    discovery.client = SimpleNamespace(responses=responses)
    trace = asyncio.run(discovery._shop_item(image, garment, crop))

    assert trace.result == parsed
    assert trace.web_search_calls == 1
    assert responses.kwargs["max_tool_calls"] == 3
    assert "include" not in responses.kwargs
    tool = responses.kwargs["tools"][0]
    assert tool["search_content_types"] == ["image", "text"]
    assert tool["image_settings"] == {"max_results": 10, "caption": True}
