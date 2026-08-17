from __future__ import annotations

import json
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import HttpUrl, ValidationError

from apps.api.app.contracts import HealthResponse, LookBuildResponse, TryOnJob
from apps.api.app.look_builder import LookBuilder
from apps.api.app.media import save_capture, save_try_on_input
from apps.api.app.openai_discovery import OpenAIDiscovery
from apps.api.app.settings import Settings
from apps.api.app.try_on import TryOnManager
from apps.api.app.youcam import YouCamClient


def create_app(
    settings: Settings | None = None, look_builder: LookBuilder | None = None
) -> FastAPI:
    app_settings = settings or Settings()
    app_settings.data_dir.mkdir(parents=True, exist_ok=True)
    app_settings.media_dir.mkdir(parents=True, exist_ok=True)

    application = FastAPI(title="WANT! API", version="0.2.0")
    application.state.settings = app_settings
    application.state.look_builder = look_builder
    application.state.try_on_manager = None
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"^(?:chrome|moz)-extension://.+$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.mount("/media", StaticFiles(directory=app_settings.media_dir), name="media")

    @application.get("/api/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        settings: Settings = request.app.state.settings
        if not settings.openai_api_key or not settings.youcam_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The OpenAI and YouCam provider keys must be configured",
            )
        return HealthResponse()

    @application.post("/api/looks", response_model=LookBuildResponse)
    async def create_look(
        request: Request,
        capture: Annotated[UploadFile, File()],
        source_url: Annotated[HttpUrl | None, Form()] = None,
    ) -> LookBuildResponse:
        look_id = str(uuid4())
        try:
            saved = await save_capture(capture, request.app.state.settings.media_dir, look_id)
            built = await get_look_builder(request).build(saved.path, look_id)
            return LookBuildResponse(
                look_id=look_id,
                source_url=source_url,
                capture_ref=saved.ref,
                result=built.result,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.post(
        "/api/try-ons", response_model=TryOnJob, status_code=status.HTTP_202_ACCEPTED
    )
    async def create_try_on(
        request: Request,
        person: Annotated[UploadFile, File()],
        look: Annotated[str, Form()],
        selections: Annotated[str, Form()],
        reference_item_ids: Annotated[str, Form()],
        references: Annotated[list[UploadFile] | None, File()] = None,
    ) -> TryOnJob:
        try:
            parsed_look = LookBuildResponse.model_validate(json.loads(look))
            parsed_selections = _selection_map(json.loads(selections))
            parsed_item_ids = _item_ids(json.loads(reference_item_ids))
            uploaded_references = references or []
            if len(parsed_item_ids) != len(uploaded_references):
                raise ValueError("Each selected item must have one uploaded reference image")

            request_id = str(uuid4())
            saved_person = await save_try_on_input(
                person,
                request.app.state.settings.media_dir,
                request_id,
                "person",
                min_side=384,
            )
            reference_refs: dict[str, str] = {}
            for index, (item_id, upload) in enumerate(
                zip(parsed_item_ids, uploaded_references, strict=True)
            ):
                saved = await save_try_on_input(
                    upload,
                    request.app.state.settings.media_dir,
                    request_id,
                    f"reference-{index}",
                )
                reference_refs[item_id] = saved.ref
            return get_try_on_manager(request).submit(
                parsed_look,
                saved_person.ref,
                parsed_selections,
                reference_refs,
            )
        except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.get("/api/try-ons/{job_id}", response_model=TryOnJob)
    def get_try_on(job_id: str, request: Request) -> TryOnJob:
        try:
            return get_try_on_manager(request).get(job_id)
        except LookupError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Try-on not found"
            ) from error
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)
            ) from error

    return application


def _selection_map(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or any(
        not isinstance(item_id, str)
        or not isinstance(rank, int)
        or isinstance(rank, bool)
        or rank < 0
        for item_id, rank in value.items()
    ):
        raise ValueError("Selections must map item IDs to non-negative product ranks")
    return value


def _item_ids(value: object) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item_id, str) or not item_id for item_id in value)
        or len(value) != len(set(value))
    ):
        raise ValueError("Reference item IDs must be a unique list of item IDs")
    return value


def get_look_builder(request: Request) -> LookBuilder:
    existing = request.app.state.look_builder
    if existing is not None:
        return existing
    settings: Settings = request.app.state.settings
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")
    request.app.state.look_builder = LookBuilder(
        OpenAIDiscovery(settings.openai_api_key),
        settings.media_dir,
    )
    return request.app.state.look_builder


def get_try_on_manager(request: Request) -> TryOnManager:
    existing = request.app.state.try_on_manager
    if existing is not None:
        return existing
    settings: Settings = request.app.state.settings
    if not settings.youcam_api_key:
        raise RuntimeError("The YouCam provider key is missing")
    request.app.state.try_on_manager = TryOnManager(
        YouCamClient(settings.youcam_api_key), settings.media_dir
    )
    return request.app.state.try_on_manager


app = create_app()
