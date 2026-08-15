from __future__ import annotations

import argparse
from pathlib import Path

from experiments.common.config import PRIVATE_OUTPUT, load_settings
from experiments.common.io import ensure_dir, normalized_image, save_lens_crop, write_json
from experiments.identification.gemini_client import GeminiLookAnalyzer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Identify garments and write safe item crops")
    parser.add_argument("image", type=Path)
    parser.add_argument("--name", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_name = args.name or args.image.stem
    output_dir = ensure_dir(PRIVATE_OUTPUT / "identification" / run_name)
    analyzer = GeminiLookAnalyzer(load_settings().require("gemini"))
    result = analyzer.analyze(args.image)
    image = normalized_image(args.image)
    width, height = image.size
    for garment in result.analysis.garments:
        ymin, xmin, ymax, xmax = garment.box_2d
        pixel_box = (
            max(0, int(xmin * width / 1000)),
            max(0, int(ymin * height / 1000)),
            min(width, int(xmax * width / 1000)),
            min(height, int(ymax * height / 1000)),
        )
        save_lens_crop(image.crop(pixel_box), output_dir / f"{garment.item_id}.jpg")
    payload = result.analysis.model_dump(mode="json")
    payload["experiment"] = {
        "model": result.model,
        "latency_seconds": round(result.latency_seconds, 3),
        "source_file": args.image.name,
    }
    write_json(output_dir / "analysis.json", payload)
    print(f"identified={len(result.analysis.garments)} latency={result.latency_seconds:.2f}s")
    print(f"artifacts={output_dir}")


if __name__ == "__main__":
    main()
