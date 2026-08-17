from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from apps.api.app.contracts import (
    GarmentAnalysis,
    ItemResult,
    LookAnalysis,
    LookResult,
    ProductMatch,
)
from apps.api.app.look_builder import BuiltLook
from apps.api.app.main import create_app
from apps.api.app.settings import ROOT, Settings


def test_firefox_extension_origin_is_allowed(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "want.sqlite3",
        media_dir=tmp_path / "media",
        migrations_dir=ROOT / "apps" / "api" / "migrations",
    )
    origin = "moz-extension://2d31a26e-1145-4dc0-b29c-80d11d12fb4a"
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin


def test_health_and_profile_round_trip(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "want.sqlite3",
        media_dir=tmp_path / "media",
        migrations_dir=ROOT / "apps" / "api" / "migrations",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok", "service": "want-api"}
        assert client.get("/api/profile").json() is None

        image_path = tmp_path / "profile.png"
        Image.new("RGB", (480, 640), "#884433").save(image_path)
        with image_path.open("rb") as image:
            response = client.post(
                "/api/profile/photo",
                files={"photo": ("profile.png", image, "image/png")},
            )
        assert response.status_code == 200
        assert response.json()["photo_ref"].startswith("/media/profile/")
        assert response.json()["photo_ref"].endswith(".jpg")
        assert client.get("/api/profile").json() == response.json()


def test_capture_builds_a_contract_valid_look(tmp_path: Path) -> None:
    class FakeLookBuilder:
        async def build(self, capture_path: Path, look_id: str) -> BuiltLook:
            assert capture_path.is_file()
            assert look_id
            return BuiltLook(
                result=LookResult(
                    analysis=LookAnalysis(
                        garments=[
                            GarmentAnalysis(
                                item_id="upper_1",
                                body_slot="upper_body",
                                category="top",
                                box_2d=[100, 100, 600, 900],
                                visibility="clear",
                                visible_fraction=1,
                                colors=["black"],
                                silhouette="fitted",
                                material_appearance="matte",
                                pattern="solid",
                                print_or_graphic="none",
                                details=[],
                            )
                        ]
                    ),
                    items=[
                        ItemResult(
                            item_id="upper_1",
                            crop_ref="/media/crop.jpg",
                            products=[
                                ProductMatch(
                                    match_kind="similar",
                                    title=f"Top {rank}",
                                    retailer="Store",
                                    product_url=f"https://example.com/top-{rank}",
                                    image_url=f"https://example.com/top-{rank}.jpg",
                                    price_minor=1000,
                                    currency="INR",
                                )
                                for rank in (1, 2)
                            ],
                        )
                    ],
                )
            )

    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "want.sqlite3",
        media_dir=tmp_path / "media",
        migrations_dir=ROOT / "apps" / "api" / "migrations",
    )
    image_path = tmp_path / "capture.png"
    profile_path = tmp_path / "profile.png"
    Image.new("RGB", (320, 480), "#884433").save(image_path)
    Image.new("RGB", (480, 640), "#884433").save(profile_path)
    with TestClient(create_app(settings, look_builder=FakeLookBuilder())) as client:
        with profile_path.open("rb") as image:
            profile_response = client.post(
                "/api/profile/photo",
                files={"photo": ("profile.png", image, "image/png")},
            )
        assert profile_response.status_code == 200
        with image_path.open("rb") as image:
            response = client.post(
                "/api/looks",
                data={"source_url": "https://example.com/look"},
                files={"capture": ("capture.png", image, "image/png")},
            )
        payload = response.json()
        payload["result"]["items"][0]["selected_index"] = 1
        saved_response = client.post(
            "/api/saved-looks",
            json={
                "source_url": payload["source_url"],
                "capture_ref": payload["capture_ref"],
                "personalized_result_ref": None,
                "snapshot": payload["result"],
            },
        )
        saved_id = saved_response.json()["id"]
        assert client.get("/api/saved-looks").json()[0]["id"] == saved_id
        saved = client.get(f"/api/saved-looks/{saved_id}")
        assert saved.status_code == 200
        assert saved.json()["snapshot"]["items"][0]["selected_index"] == 1
        assert client.delete(f"/api/saved-looks/{saved_id}").status_code == 204
    assert response.status_code == 200
    assert saved_response.status_code == 201
    assert payload["source_url"] == "https://example.com/look"
    assert payload["capture_ref"].endswith("/capture.jpg")
    assert len(payload["result"]["items"][0]["products"]) == 2
