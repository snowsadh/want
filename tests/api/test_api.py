import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from apps.api.app.contracts import (
    GarmentAnalysis,
    ItemResult,
    LookAnalysis,
    LookBuildResponse,
    LookResult,
    ProductMatch,
    TryOnJob,
)
from apps.api.app.look_builder import BuiltLook
from apps.api.app.main import create_app
from apps.api.app.settings import Settings


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        media_dir=tmp_path / "media",
        openai_api_key="test-openai",
        youcam_api_key="test-youcam",
    )


def test_health_reports_a_configured_processing_service(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for(tmp_path))) as client:
        assert client.get("/api/health").json() == {"status": "ok", "service": "want-api"}


def test_capture_builds_a_contract_valid_look_without_a_server_profile(tmp_path: Path) -> None:
    class FakeLookBuilder:
        async def build(self, capture_path: Path, look_id: str) -> BuiltLook:
            assert capture_path.is_file()
            assert look_id
            return BuiltLook(result=_look().result)

    image_path = tmp_path / "capture.png"
    Image.new("RGB", (320, 480), "#884433").save(image_path)
    with (
        TestClient(create_app(settings_for(tmp_path), look_builder=FakeLookBuilder())) as client,
        image_path.open("rb") as image,
    ):
        response = client.post(
            "/api/looks",
            data={"source_url": "https://example.com/look"},
            files={"capture": ("capture.png", image, "image/png")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_url"] == "https://example.com/look"
    assert payload["capture_ref"].endswith("/capture.jpg")
    assert len(payload["result"]["items"][0]["products"]) == 2


def test_try_on_receives_browser_owned_person_and_product_images(tmp_path: Path) -> None:
    class FakeTryOnManager:
        def submit(
            self,
            look: LookBuildResponse,
            profile_ref: str,
            selections: dict[str, int],
            reference_refs: dict[str, str],
        ) -> TryOnJob:
            assert look.look_id == _look().look_id
            assert selections == {"upper_1": 1}
            assert profile_ref.startswith("/media/try-on-inputs/")
            assert reference_refs["upper_1"].startswith("/media/try-on-inputs/")
            return TryOnJob(
                id="job-1",
                look_id=look.look_id,
                status="queued",
                stage="queued",
            )

    app = create_app(settings_for(tmp_path))
    app.state.try_on_manager = FakeTryOnManager()
    person_path = tmp_path / "person.png"
    product_path = tmp_path / "product.png"
    Image.new("RGB", (480, 640), "#884433").save(person_path)
    Image.new("RGB", (480, 640), "#111111").save(product_path)
    look = _look().model_dump(mode="json")
    look["capture_ref"] = "browser-local"
    look["result"]["items"][0]["crop_ref"] = "browser-local"

    with TestClient(app) as client, person_path.open("rb") as person, product_path.open("rb") as product:
        response = client.post(
            "/api/try-ons",
            data={
                "look": json.dumps(look),
                "selections": json.dumps({"upper_1": 1}),
                "reference_item_ids": json.dumps(["upper_1"]),
            },
            files=[
                ("person", ("person.png", person, "image/png")),
                ("references", ("product.png", product, "image/png")),
            ],
        )

    assert response.status_code == 202
    assert response.json()["id"] == "job-1"


def _look() -> LookBuildResponse:
    return LookBuildResponse(
        look_id="55dcaa77-43f1-4dca-8f7c-97246024c3f4",
        source_url="https://example.com/look",
        capture_ref="/media/capture.jpg",
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
        ),
    )
