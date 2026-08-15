from __future__ import annotations

import argparse
from pathlib import Path

from experiments.common.config import PRIVATE_OUTPUT, load_settings
from experiments.common.io import ensure_dir, write_json
from experiments.retrieval.serpapi_client import SerpApiClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Lens and text shopping discovery")
    parser.add_argument("image", type=Path, help="Garment crop below 500 KB")
    parser.add_argument("--query", required=True)
    parser.add_argument("--name", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = ensure_dir(PRIVATE_OUTPUT / "retrieval" / (args.name or args.image.stem))
    client = SerpApiClient(load_settings().require("serpapi"))
    summary: dict[str, object] = {"query": args.query, "source_crop": args.image.name, "runs": {}}
    for country in ("us", "in"):
        lens = client.lens_products(args.image, country, args.query)
        shopping = client.shopping_products(args.query, country)
        write_json(output_dir / f"{country}-lens-raw.json", lens.raw)
        write_json(output_dir / f"{country}-shopping-raw.json", shopping.raw)
        summary["runs"][country] = {
            "lens": {
                "latency_seconds": round(lens.latency_seconds, 3),
                "products": [item.model_dump(mode="json") for item in lens.products],
            },
            "shopping": {
                "latency_seconds": round(shopping.latency_seconds, 3),
                "products": [item.model_dump(mode="json") for item in shopping.products],
            },
        }
        print(
            f"{country}: lens={len(lens.products)} ({lens.latency_seconds:.2f}s) "
            f"shopping={len(shopping.products)} ({shopping.latency_seconds:.2f}s)"
        )
    write_json(output_dir / "summary.json", summary)
    print(f"artifacts={output_dir}")


if __name__ == "__main__":
    main()
