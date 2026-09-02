#!/usr/bin/env python3
"""Set the permanent response API URL for the two current PHONOS studies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    ROOT / "accent_new" / "forms.json",
    ROOT / "voice_similarity" / "trials.json",
)


def submission_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("The production API URL must be an absolute HTTPS URL")
    if not value.endswith("/api/submissions"):
        value += "/api/submissions"
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        help="Vercel deployment base URL or full /api/submissions endpoint",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Show the changes without writing the manifests",
    )
    args = parser.parse_args()
    endpoint = submission_url(args.url)

    for path in MANIFESTS:
        data = json.loads(path.read_text(encoding="utf-8"))
        previous = data.get("response_api_url", "")
        data["response_api_url"] = endpoint
        print(f"{path.relative_to(ROOT)}: {previous} -> {endpoint}")
        if not args.check:
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
