#!/usr/bin/env python3
"""Check a deployed PHONOS response API and optionally write test submissions."""

from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4


STUDIES = {
    "accent": "phonos_taslp26_accent_multidimensional",
    "voice": "phonos_taslp26_voice_similarity_abx",
}


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict, dict]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response), dict(response.headers)
    except HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} returned {error.code}: {raw}") from error


def payload(kind: str) -> dict:
    submission_id = uuid4().hex
    rows = []
    for index in range(1, 61):
        common = {
            "qid": f"TEST{index:03d}",
            "display_index": index,
            "page": (index - 1) // 5 + 1,
            "condition": "deployment_smoke_test",
            "audio": "test-only.wav",
            "response_ts": int(time.time() * 1000),
            "playback_count": 1,
        }
        if kind == "accent":
            common.update(
                naturalness_choice="synthetic",
                primary_accent="american",
                secondary_accent="none",
                secondary_influence=None,
            )
        else:
            common.update(
                abx_choice="A",
                accent_choice="A",
                similarity_rating=5,
            )
        rows.append(common)
    return {
        "submission_id": submission_id,
        "study_id": STUDIES[kind],
        "task_type": "deployment_smoke_test",
        "form_id": "A" if kind == "accent" else "",
        "participant": {
            "PROLIFIC_PID": "TEST_DEPLOYMENT",
            "STUDY_ID": "TEST_DEPLOYMENT",
            "SESSION_ID": submission_id,
        },
        "post_survey": {"comments": "TEST DEPLOYMENT - IGNORE"},
        "started_at": int(time.time() * 1000),
        "submitted_at": int(time.time() * 1000),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Vercel deployment URL")
    parser.add_argument("--write", action="store_true", help="Insert and verify tagged test submissions")
    parser.add_argument("--study", choices=["accent", "voice", "both"], default="both")
    args = parser.parse_args()

    base = args.base_url.rstrip("/") + "/"
    status, health, _ = request_json(urljoin(base, "health"))
    if status != 200 or health.get("ok") != "true":
        raise RuntimeError(f"Health check failed: {health}")
    print(f"Health OK ({health.get('database')})")

    if not args.write:
        print("Read-only check complete. Pass --write to test durable submissions.")
        return

    kinds = ("accent", "voice") if args.study == "both" else (args.study,)
    endpoint = urljoin(base, "api/submissions")
    for kind in kinds:
        test_payload = payload(kind)
        _, first, _ = request_json(endpoint, "POST", test_payload)
        _, retry, _ = request_json(endpoint, "POST", test_payload)
        _, stored, _ = request_json(
            urljoin(base, f"api/submissions/{test_payload['submission_id']}/status")
        )
        assert first == {
            "ok": True,
            "submission_id": test_payload["submission_id"],
            "rows": 60,
            "duplicate": False,
        }
        assert retry.get("duplicate") is True and retry.get("rows") == 60
        assert stored.get("stored") is True and stored.get("rows") == 60
        print(f"{kind}: first write, idempotent retry, and status check OK")


if __name__ == "__main__":
    main()
