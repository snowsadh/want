from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import HttpUrl

from apps.api.app.contracts import (
    HealthResponse,
    LookBuildResponse,
    SavedLook,
    SavedLookCreate,
    TryOnCreate,
    TryOnJob,
    UserProfile,
)
from apps.api.app.database import Database
from apps.api.app.look_builder import LookBuilder
from apps.api.app.media import save_capture, save_private_photo
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
    database = Database(app_settings.database_path, app_settings.migrations_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        yield

    application = FastAPI(title="WANT! API", version="0.1.0", lifespan=lifespan)
    application.state.database = database
    application.state.settings = app_settings
    application.state.look_builder = look_builder
    application.state.try_on_manager = None
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"^chrome-extension://[a-z]+$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    application.mount("/media", StaticFiles(directory=app_settings.media_dir), name="media")

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @application.get("/api/profile", response_model=UserProfile | None)
    def get_profile(request: Request) -> UserProfile | None:
        return get_database(request).get_profile()

    @application.post("/api/profile/photo", response_model=UserProfile)
    async def put_profile_photo(
        request: Request, photo: Annotated[UploadFile, File()]
    ) -> UserProfile:
        try:
            photo_ref = await save_private_photo(photo, request.app.state.settings.media_dir)
            return get_database(request).set_profile_photo(photo_ref)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.post("/api/looks", response_model=LookBuildResponse)
    async def create_look(
        request: Request,
        capture: Annotated[UploadFile, File()],
        source_url: Annotated[HttpUrl | None, Form()] = None,
    ) -> LookBuildResponse:
        profile = get_database(request).get_profile()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Finish local profile setup before analyzing a look",
            )
        look_id = str(uuid4())
        try:
            saved = await save_capture(capture, request.app.state.settings.media_dir, look_id)
            builder = get_look_builder(request)
            built = await builder.build(saved.path, look_id)
            response = LookBuildResponse(
                look_id=look_id,
                source_url=source_url,
                capture_ref=saved.ref,
                result=built.result,
            )
            save_look_run(request.app.state.settings, response)
            return response
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error

    @application.post("/api/try-ons", response_model=TryOnJob, status_code=status.HTTP_202_ACCEPTED)
    def create_try_on(value: TryOnCreate, request: Request) -> TryOnJob:
        profile = get_database(request).get_profile()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A local full-body photo is required for try-on",
            )
        try:
            look = load_look_run(request.app.state.settings, value.look_id)
            return get_try_on_manager(request).submit(
                look, profile.photo_ref, value.selections
            )
        except LookupError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Look not found"
            ) from error
        except ValueError as error:
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

    @application.post(
        "/api/saved-looks", response_model=SavedLook, status_code=status.HTTP_201_CREATED
    )
    def create_saved_look(value: SavedLookCreate, request: Request) -> SavedLook:
        return get_database(request).create_saved_look(value)

    @application.get("/api/saved-looks", response_model=list[SavedLook])
    def list_saved_looks(request: Request) -> list[SavedLook]:
        return get_database(request).list_saved_looks()

    @application.get("/api/saved-looks/{saved_id}", response_model=SavedLook)
    def get_saved_look(saved_id: str, request: Request) -> SavedLook:
        try:
            return get_database(request).get_saved_look(saved_id)
        except LookupError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Saved look not found"
            ) from error

    @application.delete("/api/saved-looks/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_saved_look(saved_id: str, request: Request) -> Response:
        if not get_database(request).delete_saved_look(saved_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Saved look not found"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return application


def get_database(request: Request) -> Database:
    return request.app.state.database


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


def save_look_run(settings: Settings, response: LookBuildResponse) -> None:
    destination = settings.data_dir / "look-runs" / f"{response.look_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(response.model_dump_json(indent=2))


def load_look_run(settings: Settings, look_id: str) -> LookBuildResponse:
    try:
        canonical_id = str(UUID(look_id))
    except ValueError as error:
        raise LookupError(look_id) from error
    source = Path(settings.data_dir) / "look-runs" / f"{canonical_id}.json"
    if not source.is_file():
        raise LookupError(look_id)
    payload = json.loads(source.read_text())
    result = payload.get("result")
    if isinstance(result, dict):
        result.pop("currency", None)
    return LookBuildResponse.model_validate(payload)


app = create_app()
