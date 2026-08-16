from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from apps.api.app.youcam import YouCamClient, _upload_payload


def test_small_reference_is_prepared_for_youcam_minimum(tmp_path: Path) -> None:
    source = tmp_path / "tiny.png"
    Image.new("RGB", (118, 128), "white").save(source)

    payload, content_type, file_name = _upload_payload(source)

    with Image.open(BytesIO(payload)) as prepared:
        short_side, long_side = sorted(prepared.size)
    assert short_side >= 384
    assert long_side >= 512
    assert content_type == "image/jpeg"
    assert file_name == "tiny.jpg"


def test_upload_puts_prepared_image_bytes_not_metadata(tmp_path: Path) -> None:
    source = tmp_path / "tiny.png"
    Image.new("RGB", (118, 128), "white").save(source)

    def api_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/s2s/v2.0/file/cloth-v3"
        return httpx.Response(
            200,
            json={
                "status": 200,
                "data": {
                    "files": [
                        {
                            "file_id": "file-1",
                            "requests": [{"url": "https://upload.example/image"}],
                        }
                    ]
                },
            },
        )

    def upload_handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://upload.example/image"
        with Image.open(BytesIO(request.content)) as uploaded:
            assert min(uploaded.size) >= 384
        return httpx.Response(200)

    client = YouCamClient(
        "test-key",
        client=httpx.Client(
            base_url=YouCamClient.BASE_URL,
            transport=httpx.MockTransport(api_handler),
        ),
        upload_client=httpx.Client(transport=httpx.MockTransport(upload_handler)),
    )

    assert client.upload(source) == "file-1"
