from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / "private-output" / "app"
    database_path: Path = ROOT / "private-output" / "app" / "want.sqlite3"
    media_dir: Path = ROOT / "private-output" / "app" / "media"
    migrations_dir: Path = ROOT / "apps" / "api" / "migrations"
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    youcam_api_key: str | None = os.getenv("YOUCAM_API_KEY")
