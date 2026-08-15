from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class BodySlot(StrEnum):
    UPPER_BODY = "upper_body"
    LOWER_BODY = "lower_body"
    FULL_BODY = "full_body"
    SHOES = "shoes"
    ACCESSORY = "accessory"


class Visibility(StrEnum):
    CLEAR = "clear"
    PARTIAL = "partial"
    HEAVILY_OCCLUDED = "heavily_occluded"


class Garment(BaseModel):
    item_id: str = Field(description="Stable short identifier such as upper_1")
    body_slot: BodySlot
    category: str = Field(description="Specific garment type, or unknown")
    box_2d: list[int] = Field(
        description="Tight [ymin, xmin, ymax, xmax] box normalized to 0..1000"
    )
    visibility: Visibility
    visible_fraction: float = Field(ge=0, le=1)
    colors: list[str]
    pattern: str
    material_appearance: str
    silhouette: str
    details: list[str]
    search_query: str = Field(description="Concise literal shopping query; no brand guesses")

    @field_validator("box_2d")
    @classmethod
    def validate_box(cls, value: list[int]) -> list[int]:
        if len(value) != 4 or any(point < 0 or point > 1000 for point in value):
            raise ValueError("box_2d must contain four values in 0..1000")
        ymin, xmin, ymax, xmax = value
        if ymax <= ymin or xmax <= xmin:
            raise ValueError("box_2d must have positive area")
        return value


class LookAnalysis(BaseModel):
    garments: list[Garment]
    palette: list[str]
    layering: list[str]
    missing_body_regions: list[BodySlot]
    notes: list[str] = Field(description="Only visually grounded ambiguities or limitations")


class Product(BaseModel):
    provider_id: str
    title: str
    source: str
    body_slot: BodySlot | None = None
    price: float
    currency: str
    product_url: str
    image_url: str
    region: str
    condition: str = "new"
    raw_position: int | None = None
