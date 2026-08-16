import time
from pathlib import Path

import pytest

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


def test_full_body_with_an_upper_layer_is_rejected(tmp_path: Path) -> None:
    look = _look(
        [
            _garment("dress_1", "full_body"),
            _garment("upper_1", "upper_body"),
            _garment("shoes_1", "shoes"),
        ],
        [_item("dress_1"), _item("upper_1"), _item("shoes_1")],
    )
    with pytest.raises(ValueError, match="Layered clothing"):
        TryOnManager(object(), tmp_path)._steps(look)  # type: ignore[arg-type]


def test_layered_slot_is_rejected_and_unmatched_is_not_rendered(tmp_path: Path) -> None:
    outer = _garment("coat_1", "upper_body")
    outer["category"] = "cropped jacket"
    outer["box_2d"] = [200, 200, 650, 800]
    inner = _garment("top_1", "upper_body")
    inner["category"] = "turtleneck top"
    inner["box_2d"] = [50, 50, 900, 950]
    look = _look([outer, inner], [_item("coat_1"), _item("top_1")])

    with pytest.raises(ValueError, match="Layered clothing"):
        TryOnManager(object(), tmp_path)._steps(look)  # type: ignore[arg-type]

    unmatched = _look([inner], [_item("top_1", 0)])
    assert TryOnManager(object(), tmp_path)._steps(unmatched) == []  # type: ignore[arg-type]


def test_socks_are_not_sent_as_shoes(tmp_path: Path) -> None:
    socks = _garment("socks_1", "shoes")
    socks["category"] = "crew socks"
    look = _look([socks], [_item("socks_1")])
    assert TryOnManager(object(), tmp_path)._steps(look) == []  # type: ignore[arg-type]


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
