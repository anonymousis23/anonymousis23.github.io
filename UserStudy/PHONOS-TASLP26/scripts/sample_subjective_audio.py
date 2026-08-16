#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import random
import shutil
import wave
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

SEED = 260815
QUALITY_SCORE = "nisqa_mos"
PHONOS_DEDUPE_POLICY = "dedupe by (direction, target_ref_id, source_speaker_id, utterance_id), keep highest nisqa_mos"

STUDY_ROOT = Path("/data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26")
EVAL_ROOT = Path("/data/waris/code/PHONOSv2/evaluation")
FINAL_ROOT = EVAL_ROOT / "final"
SEEDVC_ROOT = EVAL_ROOT / "generated_samples/seedvc/full"
TVTSYN_ROOT = EVAL_ROOT / "generated_samples/tvtsyn_reconstruction/full"
OUT_DIR = STUDY_ROOT / "selection_manifests"

ACCENT_GROUPS = {
    "indian": {
        "target_accent": "indian",
        "target_display": "Indian",
        "abbr": "ind",
        "directions": ("ame2ind", "ind2ame"),
        "conditions": {
            "gt_american": {"kind": "original", "accent": "american", "expected_accent": "American"},
            "gt_indian": {"kind": "original", "accent": "indian", "expected_accent": "Indian"},
            "seedvc_ame2ind": {"kind": "seedvc", "direction": "ame2ind", "expected_accent": "Indian"},
            "seedvc_ind2ame": {"kind": "seedvc", "direction": "ind2ame", "expected_accent": "American"},
            "phonos_ame2ind": {"kind": "phonos", "direction": "ame2ind", "expected_accent": "Indian"},
            "phonos_ind2ame": {"kind": "phonos", "direction": "ind2ame", "expected_accent": "American"},
        },
    },
    "british": {
        "target_accent": "british",
        "target_display": "British",
        "abbr": "bri",
        "directions": ("ame2bri", "bri2ame"),
        "conditions": {
            "gt_american": {"kind": "original", "accent": "american", "expected_accent": "American"},
            "gt_british": {"kind": "original", "accent": "british", "expected_accent": "British"},
            "seedvc_ame2bri": {"kind": "seedvc", "direction": "ame2bri", "expected_accent": "British"},
            "seedvc_bri2ame": {"kind": "seedvc", "direction": "bri2ame", "expected_accent": "American"},
            "phonos_ame2bri": {"kind": "phonos", "direction": "ame2bri", "expected_accent": "British"},
            "phonos_bri2ame": {"kind": "phonos", "direction": "bri2ame", "expected_accent": "American"},
        },
    },
    "spanish": {
        "target_accent": "spanish",
        "target_display": "Spanish-accented English",
        "abbr": "spn",
        "directions": ("ame2spn", "spn2ame"),
        "conditions": {
            "gt_american": {"kind": "original", "accent": "american", "expected_accent": "American"},
            "gt_spanish": {"kind": "original", "accent": "spanish", "expected_accent": "Spanish-accented English"},
            "seedvc_ame2spn": {"kind": "seedvc", "direction": "ame2spn", "expected_accent": "Spanish-accented English"},
            "seedvc_spn2ame": {"kind": "seedvc", "direction": "spn2ame", "expected_accent": "American"},
            "phonos_ame2spn": {"kind": "phonos", "direction": "ame2spn", "expected_accent": "Spanish-accented English"},
            "phonos_spn2ame": {"kind": "phonos", "direction": "spn2ame", "expected_accent": "American"},
        },
    },
}

PHONOS_RUNS = [
    {
        "name": "full",
        "accent": EVAL_ROOT / "metric_results/phonos_full/accentcl_full.csv",
        "nisqa": EVAL_ROOT / "metric_results/phonos_full/nisqa_full.csv",
    },
    {
        "name": "full_r1",
        "accent": EVAL_ROOT / "metric_results/phonos_r1_full/accentcl.csv",
        "nisqa": EVAL_ROOT / "metric_results/phonos_r1_full/nisqa.csv",
    },
    {
        "name": "full_r3_bri2ame",
        "accent": EVAL_ROOT / "metric_results/phonos_r3_bri2ame/accentcl.csv",
        "nisqa": EVAL_ROOT / "metric_results/phonos_r3_bri2ame/nisqa.csv",
    },
]

CSV_EXTRA_FIELDS = [
    "selected_source_path",
    "selected_item_id",
    "selected_method",
    "selected_direction",
    "selected_source_accent",
    "selected_target_accent",
    "selected_source_speaker_id",
    "selected_utterance_id",
    "selected_target_ref_id",
    "selected_phonos_run",
    "selected_accent_pred_label",
    "selected_expected_tgt_label",
    "selected_recall_tgt_hit",
    "selected_nisqa_mos",
]


def rel_to_study(path: Path) -> str:
    return path.relative_to(STUDY_ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def wav_is_readable(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 44:
        return False
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() > 0 and wf.getframerate() > 0
    except wave.Error:
        # Some generated WAVs may have non-PCM encodings readable by browsers but not wave.py.
        return path.stat().st_size > 1024


def clean_audio_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for wav in path.glob("*.wav"):
        wav.unlink()


def copy_wav(src: Path, dst: Path) -> None:
    require(src.exists(), f"Source WAV missing: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    require(wav_is_readable(dst), f"Copied WAV is missing or unreadable: {dst}")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    require(rows, f"No rows for {path}")
    fields: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sample_exact(rng: random.Random, rows: list[dict[str, Any]], n: int, label: str) -> list[dict[str, Any]]:
    require(len(rows) >= n, f"Not enough candidates for {label}: need {n}, found {len(rows)}")
    return rng.sample(rows, n)


def load_originals() -> dict[str, list[dict[str, Any]]]:
    originals: dict[str, list[dict[str, Any]]] = {}
    for accent in ["american", "british", "indian", "spanish"]:
        rows = []
        for wav in sorted((FINAL_ROOT / accent).glob("*/wav/*.wav")):
            speaker = wav.parent.parent.name
            utt = wav.stem
            rows.append({
                "method": "original",
                "condition_source": f"gt_{accent}",
                "source_path": str(wav),
                "item_id": f"gt::{accent}::{utt}",
                "direction": "reference",
                "source_accent": accent,
                "target_accent": accent,
                "source_speaker_id": speaker,
                "utterance_id": utt,
                "target_ref_id": "",
                "phonos_run": "",
                "accent_pred_label": "",
                "expected_tgt_label": "",
                "recall_tgt_hit": "",
                "nisqa_mos": "",
            })
        require(rows, f"No original WAVs found for {accent}")
        originals[accent] = rows
    return originals


def load_seedvc() -> dict[str, list[dict[str, Any]]]:
    seedvc: dict[str, list[dict[str, Any]]] = {}
    for direction_dir in sorted(SEEDVC_ROOT.iterdir()):
        if not direction_dir.is_dir():
            continue
        direction = direction_dir.name
        rows = []
        for wav in sorted(direction_dir.glob("**/*.wav")):
            parts = wav.relative_to(direction_dir).parts
            target_ref = parts[0] if len(parts) >= 3 else ""
            source_speaker = parts[-2] if len(parts) >= 2 else ""
            utt = wav.stem
            rows.append({
                "method": "seedvc",
                "condition_source": f"seedvc_{direction}",
                "source_path": str(wav),
                "item_id": f"seedvc::{direction}::{target_ref}::{source_speaker}::{utt}",
                "direction": direction,
                "source_accent": direction[:3],
                "target_accent": direction[-3:],
                "source_speaker_id": source_speaker,
                "utterance_id": utt,
                "target_ref_id": target_ref,
                "phonos_run": "",
                "accent_pred_label": "",
                "expected_tgt_label": "",
                "recall_tgt_hit": "",
                "nisqa_mos": "",
            })
        require(rows, f"No SeedVC WAVs found for {direction}")
        seedvc[direction] = rows
    return seedvc


def load_tvtsyn() -> dict[str, list[dict[str, Any]]]:
    tvtsyn: dict[str, list[dict[str, Any]]] = {}
    for accent_dir in sorted(TVTSYN_ROOT.iterdir()):
        if not accent_dir.is_dir():
            continue
        accent = accent_dir.name
        rows = []
        for wav in sorted(accent_dir.glob("**/*.wav")):
            source_speaker = wav.parent.name
            utt = wav.stem
            rows.append({
                "method": "TVTSyn",
                "condition_source": "TVTSyn",
                "source_path": str(wav),
                "item_id": f"tvtsyn::{accent}::{source_speaker}::{utt}",
                "direction": "reconstruction",
                "source_accent": accent,
                "target_accent": accent,
                "source_speaker_id": source_speaker,
                "utterance_id": utt,
                "target_ref_id": "",
                "phonos_run": "",
                "accent_pred_label": "",
                "expected_tgt_label": "",
                "recall_tgt_hit": "",
                "nisqa_mos": "",
            })
        require(rows, f"No TVTSyn WAVs found for {accent}")
        tvtsyn[accent] = rows
    return tvtsyn


def load_phonos() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    frames = []
    for run in PHONOS_RUNS:
        require(run["accent"].exists(), f"Missing PHONOS AccentCL CSV: {run['accent']}")
        require(run["nisqa"].exists(), f"Missing PHONOS NISQA CSV: {run['nisqa']}")
        accent_cols = [
            "item_id", "direction", "method", "source_accent", "target_accent", "expected_tgt_label",
            "eval_wav_path", "source_wav_path", "source_speaker_id", "utterance_id", "target_ref_id",
            "accent_pred_label", "accent_confidence", "recall_tgt_hit",
        ]
        nisqa_cols = ["item_id", "nisqa_mos", "nisqa_noi_pred", "nisqa_dis_pred", "nisqa_col_pred", "nisqa_loud_pred"]
        a = pd.read_csv(run["accent"], usecols=lambda c: c in accent_cols)
        n = pd.read_csv(run["nisqa"], usecols=lambda c: c in nisqa_cols)
        df = a.merge(n, on="item_id", how="inner", validate="one_to_one")
        df["phonos_run"] = run["name"]
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True)
    all_df["eval_exists"] = all_df["eval_wav_path"].map(lambda x: Path(str(x)).exists())
    filtered = all_df[
        (all_df["eval_exists"])
        & (all_df["recall_tgt_hit"].astype(int) == 1)
        & (all_df["accent_pred_label"] == all_df["expected_tgt_label"])
        & (all_df["nisqa_mos"].notna())
    ].copy()
    require(not filtered.empty, "No PHONOS candidates survived target-hit + NISQA filtering")
    filtered = filtered.sort_values("nisqa_mos", ascending=False)
    dedup_cols = ["direction", "target_ref_id", "source_speaker_id", "utterance_id"]
    deduped = filtered.drop_duplicates(subset=dedup_cols, keep="first").copy()
    top_by_direction = {}
    for direction, group in deduped.groupby("direction", sort=True):
        group = group.sort_values("nisqa_mos", ascending=False).head(40).copy()
        top_by_direction[direction] = group
        require(len(group) >= 10, f"PHONOS direction {direction} has fewer than 10 top candidates after filtering: {len(group)}")
    return deduped, top_by_direction


def phonos_row_to_candidate(row: pd.Series) -> dict[str, Any]:
    return {
        "method": "PHONOS",
        "condition_source": f"phonos_{row['direction']}",
        "source_path": str(row["eval_wav_path"]),
        "item_id": str(row["item_id"]),
        "direction": str(row["direction"]),
        "source_accent": str(row.get("source_accent", "")),
        "target_accent": str(row.get("target_accent", "")),
        "source_speaker_id": str(row.get("source_speaker_id", "")),
        "utterance_id": str(row.get("utterance_id", "")),
        "target_ref_id": str(row.get("target_ref_id", "")),
        "phonos_run": str(row.get("phonos_run", "")),
        "accent_pred_label": str(row.get("accent_pred_label", "")),
        "expected_tgt_label": str(row.get("expected_tgt_label", "")),
        "recall_tgt_hit": int(row.get("recall_tgt_hit", 0)),
        "nisqa_mos": float(row.get("nisqa_mos")),
    }


def selected_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_source_path": candidate.get("source_path", ""),
        "selected_item_id": candidate.get("item_id", ""),
        "selected_method": candidate.get("method", ""),
        "selected_direction": candidate.get("direction", ""),
        "selected_source_accent": candidate.get("source_accent", ""),
        "selected_target_accent": candidate.get("target_accent", ""),
        "selected_source_speaker_id": candidate.get("source_speaker_id", ""),
        "selected_utterance_id": candidate.get("utterance_id", ""),
        "selected_target_ref_id": candidate.get("target_ref_id", ""),
        "selected_phonos_run": candidate.get("phonos_run", ""),
        "selected_accent_pred_label": candidate.get("accent_pred_label", ""),
        "selected_expected_tgt_label": candidate.get("expected_tgt_label", ""),
        "selected_recall_tgt_hit": candidate.get("recall_tgt_hit", ""),
        "selected_nisqa_mos": candidate.get("nisqa_mos", ""),
    }


def select_accent_studies(rng: random.Random, originals: dict[str, list[dict[str, Any]]], seedvc: dict[str, list[dict[str, Any]]], phonos_top: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_rows = []
    summaries = {}
    phonos_top_rows = {d: [phonos_row_to_candidate(r) for _, r in df.iterrows()] for d, df in phonos_top.items()}

    for group, spec in ACCENT_GROUPS.items():
        study_dir = STUDY_ROOT / "accent" / group
        config_path = study_dir / "trials.json"
        csv_path = study_dir / "trials.csv"
        audio_dir = study_dir / "audio"
        config = json.loads(config_path.read_text())
        trials = config["trials"]
        counts = Counter(t["condition"] for t in trials)
        require(all(v == 10 for v in counts.values()), f"Unexpected condition counts for accent/{group}: {counts}")

        selected_by_condition: dict[str, list[dict[str, Any]]] = {}
        for condition, condition_spec in spec["conditions"].items():
            kind = condition_spec["kind"]
            if kind == "original":
                selected_by_condition[condition] = sample_exact(rng, originals[condition_spec["accent"]], 10, f"accent/{group}/{condition}")
            elif kind == "seedvc":
                selected_by_condition[condition] = sample_exact(rng, seedvc[condition_spec["direction"]], 10, f"accent/{group}/{condition}")
            elif kind == "phonos":
                selected_by_condition[condition] = sample_exact(rng, phonos_top_rows[condition_spec["direction"]], 10, f"accent/{group}/{condition}")
            else:
                raise ValueError(f"Unknown condition kind: {kind}")

        clean_audio_dir(audio_dir)
        used_index = defaultdict(int)
        study_rows = []
        for trial in trials:
            condition = trial["condition"]
            idx = used_index[condition]
            candidate = selected_by_condition[condition][idx]
            used_index[condition] += 1
            src_index = idx + 1
            filename = f"{trial['qid']}__{condition}__src{src_index:02d}.wav"
            dst = audio_dir / filename
            copy_wav(Path(candidate["source_path"]), dst)
            trial["source_index"] = src_index
            trial["audio_filename"] = filename
            trial["audio"] = f"audio/{filename}"
            trial.update(selected_metadata(candidate))
            study_rows.append({"study": f"accent/{group}", **trial})
            all_rows.append({"study": f"accent/{group}", **trial})

        write_json(config_path, config)
        write_csv(csv_path, trials)
        write_csv(OUT_DIR / f"accent_{group}_selection.csv", study_rows)
        summaries[f"accent/{group}"] = dict(Counter(t["condition"] for t in trials))
    return all_rows, summaries


def select_mos_study(rng: random.Random, originals: dict[str, list[dict[str, Any]]], seedvc: dict[str, list[dict[str, Any]]], tvtsyn: dict[str, list[dict[str, Any]]], phonos_top: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    study_dir = STUDY_ROOT / "mos"
    config_path = study_dir / "trials.json"
    csv_path = study_dir / "trials.csv"
    audio_dir = study_dir / "audio"
    config = json.loads(config_path.read_text())
    trials = config["trials"]
    counts = Counter(t["condition"] for t in trials)
    require(counts == {"original": 15, "PHONOS": 15, "seedvc": 15, "TVTSyn": 15}, f"Unexpected MOS condition counts: {counts}")

    original_pool = [row for rows in originals.values() for row in rows]
    seedvc_pool = [row for rows in seedvc.values() for row in rows]
    tvtsyn_pool = [row for rows in tvtsyn.values() for row in rows]
    phonos_top240 = pd.concat([df for df in phonos_top.values()], ignore_index=True)
    phonos_top100 = phonos_top240.sort_values("nisqa_mos", ascending=False).head(100)
    require(len(phonos_top100) >= 15, f"PHONOS MOS top-100 pool too small: {len(phonos_top100)}")
    phonos_pool = [phonos_row_to_candidate(r) for _, r in phonos_top100.iterrows()]

    selected_by_condition = {
        "original": sample_exact(rng, original_pool, 15, "mos/original"),
        "seedvc": sample_exact(rng, seedvc_pool, 15, "mos/seedvc"),
        "TVTSyn": sample_exact(rng, tvtsyn_pool, 15, "mos/TVTSyn"),
        "PHONOS": sample_exact(rng, phonos_pool, 15, "mos/PHONOS"),
    }

    clean_audio_dir(audio_dir)
    used_index = defaultdict(int)
    study_rows = []
    for trial in trials:
        condition = trial["condition"]
        idx = used_index[condition]
        candidate = selected_by_condition[condition][idx]
        used_index[condition] += 1
        src_index = idx + 1
        filename = f"{condition}_{src_index:02d}.wav"
        dst = audio_dir / filename
        copy_wav(Path(candidate["source_path"]), dst)
        trial["source_index"] = src_index
        trial["audio"] = f"audio/{filename}"
        trial["audio_filename"] = filename
        trial.update(selected_metadata(candidate))
        study_rows.append({"study": "mos", **trial})

    write_json(config_path, config)
    write_csv(csv_path, trials)
    write_csv(OUT_DIR / "mos_selection.csv", study_rows)
    return study_rows, {"mos": dict(Counter(t["condition"] for t in trials))}


def validate_study_audio() -> None:
    for study in ["indian", "british", "spanish"]:
        root = STUDY_ROOT / "accent" / study
        cfg = json.loads((root / "trials.json").read_text())
        for trial in cfg["trials"]:
            audio = trial.get("audio", "")
            require("placeholder" not in audio, f"Placeholder remains in accent/{study}: {audio}")
            require((root / audio).exists(), f"Missing accent/{study} audio: {audio}")
            require(wav_is_readable(root / audio), f"Unreadable accent/{study} audio: {audio}")
        counts = Counter(t["condition"] for t in cfg["trials"])
        require(all(v == 10 for v in counts.values()) and sum(counts.values()) == 60, f"Bad counts for accent/{study}: {counts}")
    root = STUDY_ROOT / "mos"
    cfg = json.loads((root / "trials.json").read_text())
    for trial in cfg["trials"]:
        audio = trial.get("audio", "")
        require("placeholder" not in audio, f"Placeholder remains in mos: {audio}")
        require((root / audio).exists(), f"Missing MOS audio: {audio}")
        require(wav_is_readable(root / audio), f"Unreadable MOS audio: {audio}")
    counts = Counter(t["condition"] for t in cfg["trials"])
    require(counts == {"original": 15, "PHONOS": 15, "seedvc": 15, "TVTSyn": 15}, f"Bad MOS counts: {counts}")


def main() -> None:
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    originals = load_originals()
    seedvc = load_seedvc()
    tvtsyn = load_tvtsyn()
    phonos_deduped, phonos_top = load_phonos()

    accent_rows, accent_summary = select_accent_studies(rng, originals, seedvc, phonos_top)
    mos_rows, mos_summary = select_mos_study(rng, originals, seedvc, tvtsyn, phonos_top)
    combined_rows = accent_rows + mos_rows
    write_csv(OUT_DIR / "subjective_audio_selection_all.csv", combined_rows)

    validate_study_audio()

    phonos_pool_counts = {direction: int(len(df)) for direction, df in phonos_top.items()}
    phonos_hit_counts = phonos_deduped.groupby("direction").size().astype(int).to_dict()
    summary = {
        "rng_seed": SEED,
        "quality_score": QUALITY_SCORE,
        "phonos_dedupe_policy": PHONOS_DEDUPE_POLICY,
        "candidate_counts": {
            "originals": {accent: len(rows) for accent, rows in originals.items()},
            "seedvc": {direction: len(rows) for direction, rows in seedvc.items()},
            "tvtsyn": {accent: len(rows) for accent, rows in tvtsyn.items()},
            "phonos_after_filter_and_dedupe": {str(k): int(v) for k, v in phonos_hit_counts.items()},
            "phonos_top_pool_by_direction": phonos_pool_counts,
        },
        "selected_counts": {**accent_summary, **mos_summary},
        "outputs": {
            "combined_selection_csv": str(OUT_DIR / "subjective_audio_selection_all.csv"),
            "selection_dir": str(OUT_DIR),
        },
    }
    write_json(OUT_DIR / "subjective_audio_selection_summary.json", summary)

    print("Subjective audio sampling complete.")
    print(f"Seed: {SEED}")
    print(f"Quality score: {QUALITY_SCORE}")
    print("PHONOS top pools:")
    for direction in sorted(phonos_pool_counts):
        print(f"  {direction}: top_pool={phonos_pool_counts[direction]} filtered_deduped={phonos_hit_counts.get(direction, 0)}")
    print("Selected counts:")
    for study, counts in {**accent_summary, **mos_summary}.items():
        print(f"  {study}: {dict(counts)}")


if __name__ == "__main__":
    main()
