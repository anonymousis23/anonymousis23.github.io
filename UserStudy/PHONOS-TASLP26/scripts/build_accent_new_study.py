#!/usr/bin/env python3
"""Build counterbalanced forms for the multidimensional accent study."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STUDY_DIR = ROOT / "accent_new"
INPUT_CSV = STUDY_DIR / "selection_manifest.csv"
SEED = 260903
FORMS = ("A", "B", "C", "D")
CONDITIONS = ("original", "phonos", "seedvc", "tvtsyn_reconstruction")
CONDITION_LABELS = {
    "original": "Original",
    "phonos": "PHONOS",
    "seedvc": "SeedVC",
    "tvtsyn_reconstruction": "TVTSyn",
}
ACCENT_LABELS = {
    "american": "American",
    "british": "British",
    "indian": "Indian",
    "spanish": "Spanish",
}

# Each direction has ten groups. These quotas total 15 of each offset globally.
OFFSET_QUOTAS = (
    (3, 3, 2, 2),
    (2, 3, 3, 2),
    (2, 2, 3, 3),
    (3, 2, 2, 3),
    (3, 2, 3, 2),
    (2, 3, 2, 3),
)


def stable_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def assign_offsets(df: pd.DataFrame) -> dict[int, int]:
    directions = sorted(df["direction"].unique())
    for attempt in range(10000):
        rng = random.Random(SEED + attempt)
        offsets: dict[int, int] = {}
        for direction, quota in zip(directions, OFFSET_QUOTAS):
            indices = sorted(df.index[df["direction"] == direction])
            slots = [offset for offset, count in enumerate(quota) for _ in range(count)]
            rng.shuffle(slots)
            offsets.update(dict(zip(indices, slots)))

        source_offsets: dict[str, set[int]] = defaultdict(set)
        valid = True
        for idx, row in df.iterrows():
            source = str(row["source_original_path"])
            if offsets[idx] in source_offsets[source]:
                valid = False
                break
            source_offsets[source].add(offsets[idx])
        if valid:
            return offsets
    raise RuntimeError("Could not assign system offsets without repeated original audio")


def order_is_valid(rows: list[dict]) -> bool:
    positions: dict[str, list[int]] = defaultdict(list)
    for pos, row in enumerate(rows):
        positions[row["source_key"]].append(pos)
    if any(b - a < 15 for values in positions.values() for a, b in zip(values, values[1:])):
        return False
    for key in ("direction", "condition"):
        if any(rows[i][key] == rows[i + 1][key] == rows[i + 2][key] for i in range(len(rows) - 2)):
            return False
    return True


def shuffled_form(rows: list[dict], form_index: int) -> list[dict]:
    for attempt in range(200000):
        rng = random.Random(SEED + 10000 * (form_index + 1) + attempt)
        candidate = rows.copy()
        rng.shuffle(candidate)
        if order_is_valid(candidate):
            return candidate
    raise RuntimeError(f"Could not construct a valid order for form {FORMS[form_index]}")


def value(row: pd.Series, name: str):
    item = row.get(name, "")
    if pd.isna(item):
        return None
    return item.item() if hasattr(item, "item") else item


def trial_for(row: pd.Series, condition: str, form_id: str) -> dict:
    if condition == "original":
        audio = value(row, "original_audio")
        item_id = f"original::{row['sample_group_id']}"
        nisqa = None
        target_ref_id = None
    elif condition == "phonos":
        audio = value(row, "phonos_audio")
        item_id = value(row, "phonos_item_id")
        nisqa = value(row, "phonos_nisqa_mos")
        target_ref_id = value(row, "phonos_target_ref_id")
    elif condition == "seedvc":
        audio = value(row, "seedvc_audio")
        item_id = value(row, "seedvc_item_id")
        nisqa = value(row, "seedvc_nisqa_mos")
        target_ref_id = value(row, "seedvc_target_ref_id")
    else:
        audio = value(row, "tvtsyn_reconstruction_audio")
        item_id = value(row, "tvtsyn_item_id")
        nisqa = value(row, "tvtsyn_nisqa_mos")
        target_ref_id = None

    source_accent = str(row["source_accent"])
    target_accent = str(row["target_accent"])
    expected_primary = source_accent if condition in {"original", "tvtsyn_reconstruction"} else target_accent
    return {
        "form_id": form_id,
        "sample_group_id": str(row["sample_group_id"]),
        "sample_id": str(row["sample_id"]),
        "source_key": stable_key(str(row["source_original_path"])),
        "source_index": int(str(row["sample_group_id"]).rsplit("S", 1)[-1]),
        "source_id": str(row["source_id"]),
        "utterance_id": str(row["utterance_id"]),
        "direction": str(row["direction"]),
        "direction_display": str(row["direction_display"]),
        "source_accent": source_accent,
        "target_accent": target_accent,
        "condition": condition,
        "condition_label": CONDITION_LABELS[condition],
        "expected_naturalness": "natural" if condition == "original" else "synthetic",
        "expected_primary_accent": expected_primary,
        "expected_accent": expected_primary,
        "audio": str(audio),
        "selected_item_id": str(item_id),
        "target_ref_id": target_ref_id,
        "nisqa_mos": nisqa,
    }


def validate(forms: dict[str, list[dict]], source_counts: Counter) -> dict:
    all_pairs = Counter()
    summary = {}
    for form_id, rows in forms.items():
        assert len(rows) == 60
        assert Counter(r["condition"] for r in rows) == Counter({c: 15 for c in CONDITIONS})
        assert set(Counter(r["direction"] for r in rows).values()) == {10}
        assert Counter(r["expected_naturalness"] for r in rows) == {"natural": 15, "synthetic": 45}
        assert len({r["sample_group_id"] for r in rows}) == 60
        originals = [r["source_key"] for r in rows if r["condition"] == "original"]
        tvtsyn = [r["source_key"] for r in rows if r["condition"] == "tvtsyn_reconstruction"]
        assert len(originals) == len(set(originals))
        assert len(tvtsyn) == len(set(tvtsyn))
        assert order_is_valid(rows)
        for row in rows:
            path = STUDY_DIR / row["audio"]
            assert path.is_file() and path.stat().st_size > 44, path
            all_pairs[(row["sample_group_id"], row["condition"])] += 1
        summary[form_id] = {
            "trials": len(rows),
            "condition_counts": dict(Counter(r["condition"] for r in rows)),
            "direction_counts": dict(Counter(r["direction"] for r in rows)),
            "naturalness_counts": dict(Counter(r["expected_naturalness"] for r in rows)),
            "unique_source_recordings": len({r["source_key"] for r in rows}),
            "repeated_original_recordings": len(originals) - len(set(originals)),
        }
    assert len(all_pairs) == 240 and set(all_pairs.values()) == {1}
    return {
        "seed": SEED,
        "forms": summary,
        "source_groups": 60,
        "globally_unique_source_recordings": len(source_counts),
        "stimuli_covered_across_forms": len(all_pairs),
        "each_group_condition_seen_once_across_forms": True,
    }


def main() -> None:
    df = pd.read_csv(INPUT_CSV).sort_values(["direction", "sample_group_id"]).reset_index(drop=True)
    if len(df) != 60:
        raise ValueError(f"Expected 60 source groups, found {len(df)}")

    offsets = assign_offsets(df)
    forms: dict[str, list[dict]] = {}
    for form_index, form_id in enumerate(FORMS):
        rows = [trial_for(row, CONDITIONS[(offsets[idx] + form_index) % 4], form_id) for idx, row in df.iterrows()]
        rows = shuffled_form(rows, form_index)
        for display_index, row in enumerate(rows, start=1):
            row["qid"] = f"{form_id}_Q{display_index:03d}"
            row["display_qid"] = f"Q{display_index:03d}"
            row["display_index"] = display_index
            row["page"] = (display_index - 1) // 5 + 1
        forms[form_id] = rows

    source_counts = Counter(str(v) for v in df["source_original_path"])
    summary = validate(forms, source_counts)
    config = {
        "study_id": "phonos_taslp26_accent_multidimensional",
        "task_type": "multidimensional_accent_verification",
        "title": "Speech Perception Study",
        "subtitle": "Listen carefully and describe each speech sample.",
        "randomized_order_seed": SEED,
        "page_size": 5,
        "cooldown_every_samples": 15,
        "cooldown_seconds": 12,
        "form_ids": list(FORMS),
        "target_usable_participants": 80,
        "response_api_url": "https://phonos-taslp26-response-api.vercel.app/api/submissions",
        "prolific_completion_urls": {form_id: "" for form_id in FORMS},
        "qualification": {
            "required_for_prolific": True,
            "url": "qualification/",
        },
        "accent_labels": ["American", "British", "Indian", "Spanish"],
        "secondary_none_value": "none",
        "influence_labels": {
            "1": "Not at all",
            "2": "Slight influence",
            "3": "Moderate influence",
            "4": "Strong influence",
            "5": "To a very large extent",
        },
        "forms": forms,
    }
    (STUDY_DIR / "forms.json").write_text(json.dumps(config, indent=2) + "\n")
    pd.DataFrame([row for rows in forms.values() for row in rows]).to_csv(STUDY_DIR / "forms.csv", index=False)
    (STUDY_DIR / "form_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
