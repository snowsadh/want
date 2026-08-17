import time
from pathlib import Path

from apps.api.app.contracts import LookBuildResponse
from apps.api.app.try_on import TryOnManager
from apps.api.app.youcam import TryOnResult


def test_selected_combination_uses_remote_urls_in_slot_order(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "profile.jpg").write_bytes(b"profile")
    look = _look(
        [
            _garment("upper_1", "upper_body"),
            _garment("lower_1", "lower_body"),
            _garment("shoes_1", "shoes"),
        ],
        [_item("upper_1", 2), _item("lower_1"), _item("shoes_1")],
    )

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def render(self, source: Path, category: str, *, reference_url: str) -> TryOnResult:
            assert source.is_file()
            self.calls.append((category, reference_url))
            return TryOnResult(
                task_id=f"task-{category}", latency_seconds=0.1, raw={}, image_bytes=b"result"
            )

    client = FakeClient()
    manager = TryOnManager(client, media)  # type: ignore[arg-type]
    job = manager.submit(look, "/media/profile.jpg", {"upper_1": 1})
    for _ in range(50):
        current = manager.get(job.id)
        if current.status in {"success", "failed"}:
            break
        time.sleep(0.01)

    assert current.status == "success"
    assert current.rendered_garment_item_ids == ["upper_1", "lower_1", "shoes_1"]
    assert client.calls == [
        ("upper_body", "https://example.com/upper_1-2.jpg"),
        ("lower_body", "https://example.com/lower_1-1.jpg"),
        ("shoes", "https://example.com/shoes_1-1.jpg"),
    ]


def test_unavailable_retailer_image_keeps_successful_preview(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "profile.jpg").write_bytes(b"profile")
    look = _look(
        [_garment("upper_1", "upper_body"), _garment("lower_1", "lower_body")],
        [_item("upper_1"), _item("lower_1")],
    )

    class FakeClient:
        def render(self, source: Path, category: str, *, reference_url: str) -> TryOnResult:
            assert source.is_file()
            if category == "lower_body":
                raise RuntimeError("YouCam task failed: error_download_image")
            return TryOnResult(
                task_id=f"task-{category}", latency_seconds=0.1, raw={}, image_bytes=b"result"
            )

    manager = TryOnManager(FakeClient(), media)  # type: ignore[arg-type]
    job = manager.submit(look, "/media/profile.jpg")
    for _ in range(50):
        current = manager.get(job.id)
        if current.status in {"success", "failed"}:
            break
        time.sleep(0.01)

    assert current.status == "success"
    assert current.result_ref is not None
    assert current.error == (
        "1 selected piece stayed out of the preview because its retailer image was unavailable "
        "to YouCam."
    )
    assert current.rendered_garment_item_ids == ["upper_1"]


def test_cached_product_image_is_uploaded_to_youcam(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "profile.jpg").write_bytes(b"profile")
    (media / "product.jpg").write_bytes(b"product")
    look = _look([_garment("upper_1", "upper_body")], [_item("upper_1")])
    look.result.items[0].products[0].image_ref = "/media/product.jpg"

    class FakeClient:
        def render(
            self,
            source: Path,
            category: str,
            *,
            reference: Path | None = None,
            reference_url: str | None = None,
        ) -> TryOnResult:
            assert source.is_file()
            assert category == "upper_body"
            assert reference == media / "product.jpg"
            assert reference_url is None
            return TryOnResult(task_id="task-upper", latency_seconds=0.1, raw={}, image_bytes=b"ok")

    manager = TryOnManager(FakeClient(), media)  # type: ignore[arg-type]
    job = manager.submit(look, "/media/profile.jpg")
    for _ in range(50):
        current = manager.get(job.id)
        if current.status in {"success", "failed"}:
            break
        time.sleep(0.01)

    assert current.status == "success"
    assert current.rendered_garment_item_ids == ["upper_1"]


def test_full_body_takes_precedence_over_separate_layers(tmp_path: Path) -> None:
    look = _look(
        [
            _garment("dress_1", "full_body"),
            _garment("upper_1", "upper_body"),
            _garment("shoes_1", "shoes"),
        ],
        [_item("dress_1"), _item("upper_1"), _item("shoes_1")],
    )
    steps = TryOnManager(object(), tmp_path)._steps(look)  # type: ignore[arg-type]

    assert [(item_id, slot.value) for item_id, slot, _reference in steps] == [
        ("dress_1", "full_body"),
        ("shoes_1", "shoes"),
    ]


def test_outer_layer_is_selected_and_unmatched_is_not_rendered(tmp_path: Path) -> None:
    outer = _garment("coat_1", "upper_body")
    outer["category"] = "cropped jacket"
    outer["box_2d"] = [200, 200, 650, 800]
    inner = _garment("top_1", "upper_body")
    inner["category"] = "turtleneck top"
    inner["box_2d"] = [50, 50, 900, 950]
    look = _look([outer, inner], [_item("coat_1"), _item("top_1")])

    steps = TryOnManager(object(), tmp_path)._steps(look)  # type: ignore[arg-type]
    assert [(item_id, slot.value) for item_id, slot, _reference in steps] == [
        ("coat_1", "upper_body")
    ]

    unmatched = _look([inner], [_item("top_1", 0)])
    assert TryOnManager(object(), tmp_path)._steps(unmatched) == []  # type: ignore[arg-type]


def test_socks_are_not_sent_as_shoes(tmp_path: Path) -> None:
    socks = _garment("socks_1", "shoes")
    socks["category"] = "crew socks"
    look = _look([socks], [_item("socks_1")])
    assert TryOnManager(object(), tmp_path)._steps(look) == []  # type: ignore[arg-type]


def test_hosiery_and_underlayers_remain_shopping_only(tmp_path: Path) -> None:
    tights = _garment("tights_1", "lower_body")
    tights["category"] = "sheer tights"
    underlayer = _garment("underlayer_1", "upper_body")
    underlayer["category"] = "lace underlayer top"
    look = _look([tights, underlayer], [_item("tights_1"), _item("underlayer_1")])

    assert TryOnManager(object(), tmp_path)._steps(look) == []  # type: ignore[arg-type]


def test_skirt_tights_socks_and_boots_form_valid_render_steps(tmp_path: Path) -> None:
    skirt = _garment("skirt_1", "lower_body")
    skirt["category"] = "asymmetrical skirt"
    tights = _garment("tights_1", "lower_body")
    tights["category"] = "sheer tights"
    socks = _garment("socks_1", "shoes")
    socks["category"] = "crew socks"
    boots = _garment("boots_1", "shoes")
    boots["category"] = "knee-high boots"
    look = _look(
        [skirt, tights, socks, boots],
        [_item("skirt_1"), _item("tights_1"), _item("socks_1"), _item("boots_1")],
    )

    steps = TryOnManager(object(), tmp_path)._steps(look)  # type: ignore[arg-type]

    assert [(item_id, slot.value) for item_id, slot, _reference in steps] == [
        ("skirt_1", "lower_body"),
        ("boots_1", "shoes"),
    ]


def _look(garments: list[dict[str, object]], items: list[dict[str, object]]) -> LookBuildResponse:
    return LookBuildResponse.model_validate(
        {
            "look_id": "55dcaa77-43f1-4dca-8f7c-97246024c3f4",
            "capture_ref": "/media/capture.jpg",
            "result": {
                "analysis": {"garments": garments},
                "items": items,
            },
        }
    )


def _garment(item_id: str, slot: str) -> dict[str, object]:
    return {
        "item_id": item_id,
        "body_slot": slot,
        "category": "test garment",
        "box_2d": [0, 0, 500, 500],
        "visibility": "clear",
        "visible_fraction": 1,
        "colors": ["black"],
        "silhouette": "regular",
        "material_appearance": "unknown",
        "pattern": "solid",
        "print_or_graphic": "none",
        "details": [],
    }


def _item(item_id: str, count: int = 1) -> dict[str, object]:
    return {
        "item_id": item_id,
        "crop_ref": f"/media/{item_id}.jpg",
        "products": [
            {
                "match_kind": "similar",
                "title": "Test product",
                "retailer": "Test store",
                "price_minor": 1000,
                "currency": "USD",
                "image_url": f"https://example.com/{item_id}-{rank}.jpg",
                "product_url": f"https://example.com/{item_id}-{rank}",
            }
            for rank in range(1, count + 1)
        ],
        "selected_index": 0,
        "give_up_reason": "No match" if count == 0 else None,
    }
