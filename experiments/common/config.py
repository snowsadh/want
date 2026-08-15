from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_INPUT = ROOT / "private-input"
PRIVATE_OUTPUT = ROOT / "private-output"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    serpapi_api_key: str | None
    youcam_api_key: str | None

    def require(self, provider: str) -> str:
        value = {
            "gemini": self.gemini_api_key,
            "serpapi": self.serpapi_api_key,
            "youcam": self.youcam_api_key,
        }.get(provider)
        if not value:
            raise ConfigError(f"Missing API key for {provider}; check .env")
        return value


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY"),
        youcam_api_key=os.getenv("YOUCAM_API_KEY"),
    )
