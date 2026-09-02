#!/usr/bin/env python3
"""Replace voice-similarity TVTSyn reconstructions with matched conversions."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import soundfile as sf


STUDY_ROOT = Path(
    "/data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26/voice_similarity"
)
RESULTS_ROOT = Path(
    "/data/waris/code/PHONOSv2/evaluation/metric_results/tvtsyn_conversion_full"
)

PUBLIC_COLUMNS = (
    "qid", "display_index", "page", "cooldown_block", "condition_label",
    "method", "direction", "direction_display", "source_accent", "target_accent",
    "source_id", "target_ref_id", "audio_a", "audio_b", "audio_x", "audio",
    "reference_a_role", "reference_b_role", "expected_choice", "expected_role",
    "expected_accent", "target_reference_was_conditioning", "nisqa_mos",
    "speaker_similarity", "source_duration_sec", "target_duration_sec",
    "synthesis_duration_sec",
)


def duration(path: str | Path) -> float:
    return float(sf.info(str(path)).duration)


def load_conversion_metrics() -> pd.DataFrame:
    manifest = pd.read_csv(RESULTS_ROOT / "metric_manifest_full.csv", keep_default_na=False)
    nisqa = pd.read_csv(RESULTS_ROOT / "nisqa_full.csv", usecols=["item_id", "nisqa_mos"])
    similarity = pd.read_csv(
        RESULTS_ROOT / "similarity_full.csv", usecols=["item_id", "spksim"]
    )
    return manifest.merge(nisqa, on="item_id", validate="one_to_one").merge(
        similarity, on="item_id", validate="one_to_one"
    )


def replace_rows(rows: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    tvtsyn_indices = rows.index[rows["method"].eq("tvtsyn")].tolist()
    if len(tvtsyn_indices) != 20:
        raise ValueError(f"Expected 20 TVTSyn trials, found {len(tvtsyn_indices)}")

    for index in tvtsyn_indices:
        old = rows.loc[index]
        matches = metrics.loc[
            metrics["direction"].eq(old["direction"])
            & metrics["target_ref_id"].eq(old["target_ref_id"])
            & metrics["utterance_id"].eq(old["source_id"])
            & metrics["source_wav_path"].eq(old["source_path"])
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one conversion for {old['qid']}, found {len(matches)}"
            )
        match = matches.iloc[0]
        synthesis_path = Path(match["eval_wav_path"])
        target_path = Path(match["target_ref_path"])
        if not synthesis_path.is_file() or not target_path.samefile(Path(old["target_path"])):
            raise ValueError(f"Invalid conversion or target reference for {old['qid']}")

        destination = STUDY_ROOT / old["audio_x"]
        shutil.copy2(synthesis_path, destination)
        expected_choice = "A" if old["reference_a_role"] == "target" else "B"
        updates = {
            "synthesis_path": str(synthesis_path),
            "expected_role": "target",
            "target_reference_was_conditioning": True,
            "nisqa_mos": float(match["nisqa_mos"]),
            "speaker_similarity": float(match["spksim"]),
            "synthesis_duration_sec": duration(synthesis_path),
            "selection_policy": (
                "matched target-conditioned TVTSyn conversion; 4-8 second source/X filtering"
            ),
            "source_item_id": str(match["item_id"]),
            "expected_choice": expected_choice,
            "expected_accent": expected_choice,
        }
        for key, value in updates.items():
            rows.at[index, key] = value
    return rows


def validate(rows: pd.DataFrame) -> None:
    assert len(rows) == 60
    assert rows.groupby("condition_label").size().to_dict() == {
        "PHONOS": 20, "SeedVC": 20, "TVTSyn": 20
    }
    tvtsyn = rows.loc[rows["method"].eq("tvtsyn")]
    assert tvtsyn["expected_role"].eq("target").all()
    assert tvtsyn["target_reference_was_conditioning"].astype(bool).all()
    assert tvtsyn["synthesis_duration_sec"].between(4.0, 8.0).all()
    assert tvtsyn["nisqa_mos"].notna().all()
    assert tvtsyn["speaker_similarity"].notna().all()
    assert tvtsyn.apply(
        lambda row: row["expected_choice"]
        == ("A" if row["reference_a_role"] == "target" else "B"), axis=1
    ).all()
    assert tvtsyn["expected_choice"].value_counts().to_dict() == {"A": 10, "B": 10}
    for column in ("audio_a", "audio_b", "audio_x"):
        assert rows[column].map(lambda path: (STUDY_ROOT / path).stat().st_size > 0).all()


def main() -> None:
    selection_path = STUDY_ROOT / "selection" / "voice_similarity_selection.csv"
    rows = pd.read_csv(selection_path, keep_default_na=False)
    rows = replace_rows(rows, load_conversion_metrics())
    validate(rows)

    rows.to_csv(selection_path, index=False)
    public = rows.loc[:, PUBLIC_COLUMNS]
    public.to_csv(STUDY_ROOT / "trials.csv", index=False)

    config_path = STUDY_ROOT / "trials.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["trials"] = public.to_dict(orient="records")
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    summary_path = STUDY_ROOT / "selection" / "selection_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["correct_choice_counts"] = {
        key: int(value) for key, value in rows.groupby("expected_choice").size().items()
    }
    summary["notes"]["tvtsyn_expected_identity"] = "target"
    summary["notes"]["tvtsyn_target_reference"] = (
        "the target reference used to condition voice conversion"
    )
    summary["notes"]["tvtsyn_source"] = str(RESULTS_ROOT)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    tvtsyn = rows.loc[rows["method"].eq("tvtsyn")]
    print(tvtsyn.groupby(["direction", "expected_choice"]).size().to_string())
    print()
    print(f"Replaced {len(tvtsyn)} TVTSyn X files with matched voice conversions.")
    print(
        "TVTSyn target-speaker similarity: "
        f"{tvtsyn['speaker_similarity'].mean():.4f} +/- "
        f"{tvtsyn['speaker_similarity'].std(ddof=1):.4f}"
    )


if __name__ == "__main__":
    main()
