#!/usr/bin/env python3
"""Prepare the 60-trial PHONOS-TASLP26 voice-similarity ABX study."""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

import pandas as pd
import soundfile as sf


STUDY_ROOT = Path(
    "/data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26/voice_similarity"
)
EVAL_ROOT = Path("/data/waris/code/PHONOSv2/evaluation")
FULL_RESULTS = EVAL_ROOT / "metric_results" / "full_eval"
PHONOS_CANDIDATES = STUDY_ROOT / "selection" / "phonos_similarity_candidates.csv"
SPEAKER_ROOT = EVAL_ROOT / "speakers"
RNG_SEED = 260830
PAGE_SIZE = 5
COOLDOWN_EVERY = 15

DIRECTIONS = ("ame2bri", "ame2ind", "ame2spn", "bri2ame", "ind2ame", "spn2ame")
ACCENTS_BY_DIRECTION = {
    "ame2bri": ("american", "british"),
    "ame2ind": ("american", "indian"),
    "ame2spn": ("american", "spanish"),
    "bri2ame": ("british", "american"),
    "ind2ame": ("indian", "american"),
    "spn2ame": ("spanish", "american"),
}
BASELINE_QUOTAS = {
    "ame2bri": 4,
    "ame2ind": 4,
    "ame2spn": 3,
    "bri2ame": 3,
    "ind2ame": 3,
    "spn2ame": 3,
}
PHONOS_QUOTAS = {
    "ame2bri": 2,
    "ame2ind": 4,
    "ame2spn": 2,
    "bri2ame": 4,
    "ind2ame": 4,
    "spn2ame": 4,
}
TARGET_REFERENCE_DIRS = {
    "american": SPEAKER_ROOT / "ame",
    "british": SPEAKER_ROOT / "bri",
    "indian": SPEAKER_ROOT / "ind",
    "spanish": SPEAKER_ROOT / "spn",
}
METHOD_LABELS = {"seedvc": "SeedVC", "tvtsyn": "TVTSyn", "phonos": "PHONOS"}


duration_cache: dict[str, float] = {}


def duration(path: str | Path) -> float:
    key = str(path)
    if key not in duration_cache:
        duration_cache[key] = float(sf.info(key).duration)
    return duration_cache[key]


def valid_audio(path: str | Path) -> bool:
    candidate = Path(path)
    return candidate.is_file() and candidate.stat().st_size > 0


def read_baseline_metrics() -> pd.DataFrame:
    similarity = pd.read_csv(FULL_RESULTS / "similarity_full.csv", keep_default_na=False)
    nisqa = pd.read_csv(FULL_RESULTS / "nisqa_full.csv", usecols=["item_id", "nisqa_mos"])
    return similarity.merge(nisqa, on="item_id", how="left", validate="one_to_one")


def sample_baseline(method: str, metrics: pd.DataFrame, rng: random.Random) -> list[dict]:
    candidates = metrics.loc[metrics["method"].eq(method)].copy()
    candidates = candidates.loc[
        candidates["eval_wav_path"].map(valid_audio)
        & candidates["source_wav_path"].map(valid_audio)
    ].copy()
    candidates["source_duration_sec"] = candidates["source_wav_path"].map(duration)
    candidates["synthesis_duration_sec"] = candidates["eval_wav_path"].map(duration)
    candidates = candidates.loc[
        candidates["source_duration_sec"].between(4.0, 8.0)
        & candidates["synthesis_duration_sec"].between(4.0, 8.0)
    ].copy()

    selected: list[dict] = []
    used_sources: set[str] = set()
    used_outputs: set[str] = set()
    for direction in DIRECTIONS:
        pool = candidates.loc[candidates["direction"].eq(direction)].copy()
        indices = pool.index.tolist()
        rng.shuffle(indices)
        count = 0
        for index in indices:
            row = pool.loc[index]
            source_path = str(row["source_wav_path"])
            output_path = str(row["eval_wav_path"])
            if source_path in used_sources or output_path in used_outputs:
                continue
            if method == "seedvc":
                target_path = str(row["target_ref_path"])
                target_id = str(row["target_ref_id"])
                if not valid_audio(target_path):
                    continue
                conditioned_on_target = True
                expected_role = "target"
            else:
                references = sorted(TARGET_REFERENCE_DIRS[str(row["target_accent"])].glob("*.wav"))
                if not references:
                    raise ValueError(f"No target references for {row['target_accent']}")
                target = rng.choice(references)
                target_path = str(target)
                target_id = target.stem
                conditioned_on_target = False
                expected_role = "source"
            selected.append(
                {
                    "method": method,
                    "condition_label": METHOD_LABELS[method],
                    "direction": direction,
                    "direction_display": str(row["direction_display"]),
                    "source_accent": str(row["source_accent"]),
                    "target_accent": str(row["target_accent"]),
                    "source_id": str(row["utterance_id"]),
                    "source_path": source_path,
                    "target_path": target_path,
                    "target_ref_id": target_id,
                    "synthesis_path": output_path,
                    "expected_role": expected_role,
                    "target_reference_was_conditioning": conditioned_on_target,
                    "nisqa_mos": float(row["nisqa_mos"]),
                    "speaker_similarity": float(row["spksim"]),
                    "source_duration_sec": float(row["source_duration_sec"]),
                    "target_duration_sec": duration(target_path),
                    "synthesis_duration_sec": float(row["synthesis_duration_sec"]),
                    "selection_policy": "random after 4-8 second source/X filtering",
                    "source_item_id": str(row["item_id"]),
                }
            )
            used_sources.add(source_path)
            used_outputs.add(output_path)
            count += 1
            if count == BASELINE_QUOTAS[direction]:
                break
        if count != BASELINE_QUOTAS[direction]:
            raise ValueError(f"Could not sample {BASELINE_QUOTAS[direction]} {method}/{direction}")
    return selected


def sample_phonos() -> list[dict]:
    candidates = pd.read_csv(PHONOS_CANDIDATES, keep_default_na=False)
    candidates = candidates.loc[
        candidates["recall_tgt_hit"].eq(1)
        & candidates["nisqa_mos"].ge(4.0)
        & candidates["target_spksim"].ge(0.84)
        & candidates["source_duration_sec"].between(4.0, 8.0)
        & candidates["synthesis_duration_sec"].between(4.0, 8.0)
    ].copy()
    candidates["quality_percentile"] = candidates.groupby("direction")["nisqa_mos"].rank(pct=True)
    candidates["similarity_percentile"] = candidates.groupby("direction")["target_spksim"].rank(pct=True)
    candidates["joint_rank"] = candidates[
        ["quality_percentile", "similarity_percentile"]
    ].min(axis=1)
    candidates["mean_rank"] = candidates[
        ["quality_percentile", "similarity_percentile"]
    ].mean(axis=1)

    selected: list[dict] = []
    used_sources: set[str] = set()
    # The two scarce American target directions are assigned first.
    order = ("ame2bri", "ame2spn", "ame2ind", "bri2ame", "ind2ame", "spn2ame")
    for direction in order:
        pool = candidates.loc[candidates["direction"].eq(direction)].sort_values(
            ["joint_rank", "mean_rank", "nisqa_mos", "target_spksim"],
            ascending=False,
            kind="stable",
        )
        count = 0
        for row in pool.itertuples(index=False):
            if row.source_original_path in used_sources:
                continue
            selected.append(
                {
                    "method": "phonos",
                    "condition_label": "PHONOS",
                    "direction": row.direction,
                    "direction_display": row.direction_display,
                    "source_accent": ACCENTS_BY_DIRECTION[direction][0],
                    "target_accent": ACCENTS_BY_DIRECTION[direction][1],
                    "source_id": row.source_id,
                    "source_path": row.source_original_path,
                    "target_path": row.target_ref_path,
                    "target_ref_id": row.target_reference,
                    "synthesis_path": row.synthesis_original_path,
                    "expected_role": "target",
                    "target_reference_was_conditioning": True,
                    "nisqa_mos": float(row.nisqa_mos),
                    "speaker_similarity": float(row.target_spksim),
                    "source_duration_sec": float(row.source_duration_sec),
                    "target_duration_sec": float(row.target_duration_sec),
                    "synthesis_duration_sec": float(row.synthesis_duration_sec),
                    "selection_policy": (
                        "manual acceptance + target AccentCL hit + NISQA>=4.0 + "
                        "target speaker similarity>=0.84; ranked jointly"
                    ),
                    "source_item_id": row.selected_item_id,
                    "quality_percentile": float(row.quality_percentile),
                    "similarity_percentile": float(row.similarity_percentile),
                    "joint_rank": float(row.joint_rank),
                }
            )
            used_sources.add(row.source_original_path)
            count += 1
            if count == PHONOS_QUOTAS[direction]:
                break
        if count != PHONOS_QUOTAS[direction]:
            raise ValueError(f"Could not select {PHONOS_QUOTAS[direction]} PHONOS/{direction}")
    return selected


def publish_trials(rows: list[dict], rng: random.Random) -> list[dict]:
    audio_dir = STUDY_ROOT / "audio"
    if audio_dir.exists():
        shutil.rmtree(audio_dir)
    audio_dir.mkdir(parents=True)
    rng.shuffle(rows)
    correct_choices = ["A"] * 30 + ["B"] * 30
    rng.shuffle(correct_choices)
    published = []
    for display_index, (row, correct_choice) in enumerate(zip(rows, correct_choices), start=1):
        qid = f"Q{display_index:03d}"
        other_role = "source" if row["expected_role"] == "target" else "target"
        role_a = row["expected_role"] if correct_choice == "A" else other_role
        role_b = other_role if correct_choice == "A" else row["expected_role"]
        paths = {"source": row["source_path"], "target": row["target_path"]}
        destinations = {
            "audio_a": audio_dir / f"{qid}_A.wav",
            "audio_b": audio_dir / f"{qid}_B.wav",
            "audio_x": audio_dir / f"{qid}_X.wav",
        }
        shutil.copy2(paths[role_a], destinations["audio_a"])
        shutil.copy2(paths[role_b], destinations["audio_b"])
        shutil.copy2(row["synthesis_path"], destinations["audio_x"])
        trial = {
            **row,
            "qid": qid,
            "display_index": display_index,
            "page": (display_index - 1) // PAGE_SIZE + 1,
            "cooldown_block": (display_index - 1) // COOLDOWN_EVERY + 1,
            "audio_a": f"audio/{qid}_A.wav",
            "audio_b": f"audio/{qid}_B.wav",
            "audio_x": f"audio/{qid}_X.wav",
            "audio": f"audio/{qid}_X.wav",
            "reference_a_role": role_a,
            "reference_b_role": role_b,
            "expected_choice": correct_choice,
            "expected_accent": correct_choice,
        }
        published.append(trial)
    return published


def public_trial(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "qid", "display_index", "page", "cooldown_block", "condition_label",
            "method", "direction", "direction_display", "source_accent", "target_accent",
            "source_id", "target_ref_id", "audio_a", "audio_b", "audio_x", "audio",
            "reference_a_role", "reference_b_role", "expected_choice", "expected_role",
            "expected_accent", "target_reference_was_conditioning", "nisqa_mos",
            "speaker_similarity", "source_duration_sec", "target_duration_sec",
            "synthesis_duration_sec",
        )
    }


def write_outputs(rows: list[dict]) -> None:
    STUDY_ROOT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(STUDY_ROOT / "selection" / "voice_similarity_selection.csv", index=False)
    public_rows = [public_trial(row) for row in rows]
    pd.DataFrame(public_rows).to_csv(STUDY_ROOT / "trials.csv", index=False)
    config = {
        "study_id": "phonos_taslp26_voice_similarity_abx",
        "task_type": "voice_similarity_abx",
        "title": "Voice Similarity Study",
        "subtitle": "Compare the voice identity of converted speech with two reference speakers.",
        "page_size": PAGE_SIZE,
        "cooldown_every_samples": COOLDOWN_EVERY,
        "cooldown_seconds": 12,
        "randomized_order_seed": RNG_SEED,
        "response_api_url": "https://juggle-rematch-marry.ngrok-free.dev/api/submissions",
        "apps_script_webapp_url": "",
        "prolific_completion_url": "",
        "trials": public_rows,
    }
    (STUDY_ROOT / "trials.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    frame = pd.DataFrame(rows)
    summary = {
        "rng_seed": RNG_SEED,
        "trial_count": len(rows),
        "method_counts": frame.groupby("condition_label").size().to_dict(),
        "method_direction_counts": {
            f"{method}/{direction}": int(count)
            for (method, direction), count in frame.groupby(["condition_label", "direction"]).size().items()
        },
        "correct_choice_counts": frame.groupby("expected_choice").size().to_dict(),
        "duration_filter_sec": [4.0, 8.0],
        "phonos_filters": {
            "manually_accepted": True,
            "target_accentcl_hit": True,
            "nisqa_mos_min": 4.0,
            "target_speaker_similarity_min": 0.84,
            "unique_source_utterances": True,
        },
        "notes": {
            "seedvc_expected_identity": "target",
            "phonos_expected_identity": "target",
            "tvtsyn_expected_identity": "source",
            "tvtsyn_target_reference": "unconditioned distractor from the nominal target accent",
        },
    }
    (STUDY_ROOT / "selection" / "selection_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def validate(rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    assert len(frame) == 60
    assert frame.groupby("condition_label").size().to_dict() == {
        "PHONOS": 20, "SeedVC": 20, "TVTSyn": 20
    }
    assert frame.groupby("expected_choice").size().to_dict() == {"A": 30, "B": 30}
    assert frame["source_duration_sec"].between(4.0, 8.0).all()
    assert frame["synthesis_duration_sec"].between(4.0, 8.0).all()
    phonos = frame.loc[frame["condition_label"].eq("PHONOS")]
    assert phonos["nisqa_mos"].ge(4.0).all()
    assert phonos["speaker_similarity"].ge(0.84).all()
    assert phonos["source_path"].nunique() == 20
    for column in ("audio_a", "audio_b", "audio_x"):
        assert frame[column].map(lambda value: valid_audio(STUDY_ROOT / value)).all()


def main() -> None:
    rng = random.Random(RNG_SEED)
    metrics = read_baseline_metrics()
    selected = sample_baseline("seedvc", metrics, rng)
    selected.extend(sample_baseline("tvtsyn", metrics, rng))
    selected.extend(sample_phonos())
    rows = publish_trials(selected, rng)
    validate(rows)
    write_outputs(rows)
    frame = pd.DataFrame(rows)
    print(frame.groupby(["condition_label", "direction"]).size().to_string())
    print("\nCorrect answer balance:")
    print(frame.groupby("expected_choice").size().to_string())
    print(f"\nWrote {len(rows)} trials and {3 * len(rows)} WAV files to {STUDY_ROOT}")


if __name__ == "__main__":
    main()
