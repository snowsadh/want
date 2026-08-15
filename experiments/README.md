# WANT! experiment harness

This directory contains disposable, measured spikes for the three risky external
boundaries. It is not the application scaffold.

All personal inputs, provider payloads, uploaded-image identifiers, and generated
images stay under `private-input/` or `private-output/`, both ignored by Git.

## Setup

```bash
uv sync --extra dev
```

The repository-root `.env` must define the three keys listed in `.env.example`.

## Structured identification

```bash
uv run python -m experiments.identification.run \
  private-input/user-img/image3.jpg --name user-image3
```

The command writes schema-validated analysis plus one sub-500 KB crop per item.

## Live candidate discovery

```bash
uv run python -m experiments.retrieval.run \
  private-output/identification/user-image3/upper_1.jpg \
  --query "red cropped tie front cardigan" --name user-image3-upper
```

The command compares Lens image search and Google Shopping text search for US/USD
and India/INR. Normalization rejects missing price/image/link data and explicit
second-hand condition markers.

## YouCam Clothes v3

```bash
uv run python -m experiments.youcam.run \
  private-input/user-img/image3.jpg \
  --reference private-input/reference/example.png \
  --category full_body --name image3-full-body
```

The client follows the current v3 signed-upload and async-task flow, immediately
downloads the temporary result, and excludes the signed URL from its summary.

## Ranking add-on

Install the local FashionSigLIP experiment only when candidate discovery is known
to return useful products:

```bash
uv sync --extra dev --extra ranking
```

For this small experiment, embeddings will be compared with an in-memory NumPy
matrix. No vector database or service is involved.
