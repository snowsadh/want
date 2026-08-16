import pytest
from pydantic import ValidationError

from apps.api.app.contracts import BodySlot, GarmentAnalysis, Visibility


def garment(**overrides: object) -> GarmentAnalysis:
    values = {
        "item_id": "upper_1",
        "body_slot": BodySlot.UPPER_BODY,
        "category": "cardigan",
        "box_2d": [100, 100, 600, 700],
        "visibility": Visibility.CLEAR,
        "visible_fraction": 0.9,
        "colors": ["red"],
        "pattern": "solid",
        "print_or_graphic": "none",
        "material_appearance": "knit",
        "silhouette": "cropped",
        "details": ["tie front"],
    }
    values.update(overrides)
    return GarmentAnalysis.model_validate(values)


def test_garment_accepts_valid_normalized_box() -> None:
    assert garment().box_2d == [100, 100, 600, 700]


@pytest.mark.parametrize(
    "box",
    ([100, 100, 90, 700], [100, 100, 600], [-1, 0, 10, 10], [0, 0, 1001, 10]),
)
def test_garment_rejects_invalid_box(box: list[int]) -> None:
    with pytest.raises(ValidationError):
        garment(box_2d=box)
