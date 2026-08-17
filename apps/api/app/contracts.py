from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class MatchKind(StrEnum):
    EXACT = "exact"
    SIMILAR = "similar"


class TryOnStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "want-api"


class UserProfile(BaseModel):
    photo_ref: str
    created_at: datetime
    updated_at: datetime


class GarmentAnalysis(StrictModel):
    item_id: str
    body_slot: BodySlot
    category: str
    box_2d: list[int]
    visibility: Visibility
    visible_fraction: float = Field(ge=0, le=1)
    colors: list[str]
    silhouette: str
    material_appearance: str
    pattern: str
    print_or_graphic: str
    details: list[str]

    @field_validator("box_2d")
    @classmethod
    def validate_box(cls, value: list[int]) -> list[int]:
        if len(value) != 4 or any(point < 0 or point > 1000 for point in value):
            raise ValueError("box_2d must contain four normalized values")
        ymin, xmin, ymax, xmax = value
        if ymax <= ymin or xmax <= xmin:
            raise ValueError("box_2d must have positive area")
        return value


class LookAnalysis(StrictModel):
    garments: list[GarmentAnalysis]

    @model_validator(mode="after")
    def unique_items(self) -> LookAnalysis:
        ids = [item.item_id for item in self.garments]
        if len(ids) != len(set(ids)):
            raise ValueError("inventory item IDs must be unique")
        return self


class ProductMatch(StrictModel):
    match_kind: MatchKind
    title: str
    retailer: str
    product_url: HttpUrl
    image_url: HttpUrl
    image_ref: str | None = None
    price_minor: int | None = Field(ge=0)
    currency: str | None

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        currency = value.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        return currency

    @model_validator(mode="after")
    def price_is_paired(self) -> ProductMatch:
        if (self.price_minor is None) != (self.currency is None):
            raise ValueError("price and currency must both be present or both be null")
        return self


class ItemResult(StrictModel):
    item_id: str
    crop_ref: str
    products: list[ProductMatch] = Field(max_length=3)
    selected_index: int = 0
    give_up_reason: str | None = None

    @model_validator(mode="after")
    def valid_selection(self) -> ItemResult:
        if self.products and not 0 <= self.selected_index < len(self.products):
            raise ValueError("selected_index must identify a returned product")
        if not self.products:
            self.selected_index = 0
        return self


class LookResult(StrictModel):
    analysis: LookAnalysis
    items: list[ItemResult]

    @model_validator(mode="after")
    def one_result_per_item(self) -> LookResult:
        inventory = [item.item_id for item in self.analysis.garments]
        results = [item.item_id for item in self.items]
        if len(results) != len(set(results)) or set(results) != set(inventory):
            raise ValueError("every inventory item must have exactly one result row")
        return self


class LookBuildResponse(StrictModel):
    look_id: str
    source_url: HttpUrl | None = None
    capture_ref: str
    result: LookResult


class TryOnCreate(StrictModel):
    look_id: str
    selections: dict[str, int] = Field(default_factory=dict)

    @field_validator("selections")
    @classmethod
    def non_negative_ranks(cls, value: dict[str, int]) -> dict[str, int]:
        if any(rank < 0 for rank in value.values()):
            raise ValueError("selected ranks must be non-negative")
        return value


class TryOnJob(StrictModel):
    id: str
    look_id: str
    status: TryOnStatus
    stage: str
    result_ref: str | None = None
    error: str | None = None
    rendered_garment_item_ids: list[str] = Field(default_factory=list)


class SavedLookCreate(StrictModel):
    source_url: HttpUrl | None = None
    capture_ref: str
    personalized_result_ref: str | None = None
    snapshot: LookResult


class SavedLook(SavedLookCreate):
    id: str
    created_at: datetime
    updated_at: datetime
