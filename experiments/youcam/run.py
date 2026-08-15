from __future__ import annotations

import argparse
from pathlib import Path

from experiments.common.config import PRIVATE_OUTPUT, load_settings
from experiments.common.io import ensure_dir, write_json
from experiments.youcam.client import YouCamClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one YouCam Clothes v3 try-on")
    parser.add_argument("source", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-url")
    parser.add_argument(
        "--category", choices=("upper_body", "lower_body", "full_body"), required=True
    )
    parser.add_argument("--name", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = ensure_dir(PRIVATE_OUTPUT / "youcam" / args.name)
    client = YouCamClient(load_settings().require("youcam"))
    result = client.render(
        args.source,
        args.category,
        reference=args.reference,
        reference_url=args.reference_url,
    )
    image_path = output_dir / "result.jpg"
    image_path.write_bytes(result.image_bytes)
    # Deliberately omit the provider's temporary signed result URL.
    write_json(
        output_dir / "summary.json",
        {
            "task_id": result.task_id,
            "category": args.category,
            "source_file": args.source.name,
            "reference_file": args.reference.name if args.reference else None,
            "reference_is_remote": bool(args.reference_url),
            "latency_seconds": round(result.latency_seconds, 3),
            "task_status": (result.raw.get("data") or {}).get("task_status"),
            "error": (result.raw.get("data") or {}).get("error"),
        },
    )
    print(f"status=success latency={result.latency_seconds:.2f}s")
    print(f"result={image_path}")


if __name__ == "__main__":
    main()
