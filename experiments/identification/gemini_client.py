from __future__ import annotations

import base64
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path

from google import genai

from experiments.common.models import LookAnalysis

PROMPT = """
Analyze only the clothing visibly worn by the main person in this image.

Return one item per separately retrievable garment, shoe pair, or meaningful accessory.
Use tight boxes in [ymin, xmin, ymax, xmax] order normalized to 0..1000. Do not include the
face or unrelated background in a box unless unavoidable. Describe only visible evidence:
never guess a brand, exact fabric composition, hidden construction, or an unseen body region.
Use "unknown" when a visual attribute cannot be supported. Keep search_query literal and
useful for shopping. Mark body regions not shown well enough to identify clothing. If a dress
or jumpsuit is one continuous garment, use full_body rather than inventing separate pieces.
""".strip()


@dataclass(frozen=True)
class GeminiResult:
    analysis: LookAnalysis
    latency_seconds: float
    model: str


class GeminiLookAnalyzer:
    def __init__(self, api_key: str, model: str = "gemini-3.6-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self.model = model

    def analyze(self, image_path: Path) -> GeminiResult:
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        started = time.perf_counter()
        interaction = self._client.interactions.create(
            model=self.model,
            input=[
                {"type": "text", "text": PROMPT},
                {"type": "image", "data": encoded, "mime_type": mime_type},
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": LookAnalysis.model_json_schema(),
            },
            generation_config={"thinking_level": "minimal"},
        )
        latency = time.perf_counter() - started
        analysis = LookAnalysis.model_validate_json(interaction.output_text)
        return GeminiResult(analysis=analysis, latency_seconds=latency, model=self.model)
