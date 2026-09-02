#!/usr/bin/env python3
"""Prepare matched accent-verification samples from the reviewed PHONOS shortlist."""

from __future__ import annotations

import hashlib
import json
import posixpath
import random
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pandas as pd
import soundfile as sf


PROJECT_ROOT = Path("/data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26")
OUTPUT_ROOT = PROJECT_ROOT / "accent_new"
INPUT_WORKBOOK = PROJECT_ROOT / "accent" / "PHONOS_Conversions_shortlisted.xlsx"
PHONOS_REVIEW_MANIFEST = PROJECT_ROOT / "accent" / "phonos_review_samples" / "manifest.csv"
EVAL_ROOT = Path("/data/waris/code/PHONOSv2/evaluation")
BASELINE_RESULTS = EVAL_ROOT / "metric_results" / "full_eval"
BASE_URL = "https://anonymousis23.github.io/UserStudy/PHONOS-TASLP26/accent_new"
RNG_SEED = 260902
SAMPLES_PER_DIRECTION = 10

SHEET_DIRECTIONS = {
    "AME to BRE": "ame2bri",
    "AME to INE": "ame2ind",
    "AME to SPE": "ame2spn",
    "BRE to AME": "bri2ame",
    "INE to AME": "ind2ame",
    "SPE to AME": "spn2ame",
}
DIRECTION_DISPLAY = {
    "ame2bri": "American to British",
    "ame2ind": "American to Indian",
    "ame2spn": "American to Spanish",
    "bri2ame": "British to American",
    "ind2ame": "Indian to American",
    "spn2ame": "Spanish to American",
}
DIRECTION_ACCENTS = {
    "ame2bri": ("american", "british"),
    "ame2ind": ("american", "indian"),
    "ame2spn": ("american", "spanish"),
    "bri2ame": ("british", "american"),
    "ind2ame": ("indian", "american"),
    "spn2ame": ("spanish", "american"),
}
TARGET_DIR = {"american": "ame", "british": "bri", "indian": "ind", "spanish": "spn"}
AUDIO_LABELS = {
    "original": "Original",
    "phonos": "PHONOS",
    "seedvc": "SeedVC",
    "tvtsyn_reconstruction": "TVTSyn Reconstruction",
}

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def cell_column(reference: str) -> str:
    match = re.match(r"[A-Z]+", reference)
    if not match:
        raise ValueError(f"Invalid XLSX cell reference: {reference}")
    return match.group()


def shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
        for item in root.findall(f"{{{MAIN_NS}}}si")
    ]


def read_cell(cell: ET.Element, strings: list[str]) -> str:
    value = cell.find(f"{{{MAIN_NS}}}v")
    cell_type = cell.attrib.get("t")
    if cell_type == "s" and value is not None:
        return strings[int(value.text or 0)]
    if cell_type == "inlineStr":
        inline = cell.find(f"{{{MAIN_NS}}}is")
        if inline is not None:
            return "".join(node.text or "" for node in inline.iter(f"{{{MAIN_NS}}}t"))
    return value.text if value is not None and value.text is not None else ""


def parse_shortlist_workbook(path: Path) -> dict[str, list[dict[str, str]]]:
    with ZipFile(path) as archive:
        strings = shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        parsed: dict[str, list[dict[str, str]]] = {}
        sheets = workbook.find(f"{{{MAIN_NS}}}sheets")
        if sheets is None:
            raise ValueError("Workbook contains no sheets")
        for sheet in sheets:
            sheet_name = sheet.attrib["name"]
            if sheet_name not in SHEET_DIRECTIONS:
                continue
            rel_id = sheet.attrib[f"{{{DOC_REL_NS}}}id"]
            target = targets[rel_id].lstrip("/")
            if not target.startswith("xl/"):
                target = posixpath.normpath(posixpath.join("xl", target))
            root = ET.fromstring(archive.read(target))
            rows: list[dict[str, str]] = []
            for row in root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"):
                values = {
                    cell_column(cell.attrib["r"]): read_cell(cell, strings).strip()
                    for cell in row.findall(f"{{{MAIN_NS}}}c")
                }
                if not values.get("A") or values.get("A") == "Question No.":
                    continue
                required = ("A", "B", "C", "D")
                if not all(values.get(column) for column in required):
                    raise ValueError(f"Incomplete shortlisted row in {sheet_name}: {values}")
                rows.append(
                    {
                        "question_no": values["A"],
                        "transcript": values["B"],
                        "source_audio_url": values["C"],
                        "synthesis_audio_url": values["D"],
                    }
                )
            parsed[SHEET_DIRECTIONS[sheet_name]] = rows
    missing = set(SHEET_DIRECTIONS.values()) - set(parsed)
    if missing:
        raise ValueError(f"Missing shortlist sheets: {sorted(missing)}")
    return parsed


def question_number(value: str) -> int:
    match = re.fullmatch(r"Q(\d+)", value)
    if not match:
        raise ValueError(f"Invalid question number: {value}")
    return int(match.group(1))


def published_local_path(url: str) -> Path:
    parsed = urlparse(url)
    prefix = "/UserStudy/PHONOS-TASLP26/"
    if parsed.netloc != "anonymousis23.github.io" or not parsed.path.startswith(prefix):
        raise ValueError(f"Unexpected published URL: {url}")
    return PROJECT_ROOT / unquote(parsed.path[len(prefix):])


def wav_info(path: Path) -> tuple[float, int, int]:
    info = sf.info(str(path))
    return float(info.duration), int(info.samplerate), int(info.channels)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_baseline_metrics() -> pd.DataFrame:
    manifest = pd.read_csv(BASELINE_RESULTS / "metric_manifest_full.csv", keep_default_na=False)
    nisqa = pd.read_csv(BASELINE_RESULTS / "nisqa_full.csv", usecols=["item_id", "nisqa_mos"])
    accent = pd.read_csv(
        BASELINE_RESULTS / "accentcl_full.csv",
        usecols=["item_id", "accent_pred_label", "recall_tgt_hit", "recall_src_hit"],
    )
    return manifest.merge(nisqa, on="item_id", how="left", validate="one_to_one").merge(
        accent, on="item_id", how="left", validate="one_to_one"
    )


def choose_shortlist(shortlists: dict[str, list[dict[str, str]]]) -> tuple[list[dict], dict]:
    rng = random.Random(RNG_SEED)
    selected: list[dict] = []
    counts: dict[str, dict[str, int]] = {}
    for direction in SHEET_DIRECTIONS.values():
        candidates = sorted(shortlists[direction], key=lambda row: question_number(row["question_no"]))
        if len(candidates) < SAMPLES_PER_DIRECTION:
            raise ValueError(
                f"{direction} has {len(candidates)} shortlisted rows; need {SAMPLES_PER_DIRECTION}"
            )
        chosen = candidates if len(candidates) == SAMPLES_PER_DIRECTION else rng.sample(
            candidates, SAMPLES_PER_DIRECTION
        )
        chosen = sorted(chosen, key=lambda row: question_number(row["question_no"]))
        selected.extend({**row, "direction": direction} for row in chosen)
        counts[direction] = {"shortlisted": len(candidates), "selected": len(chosen)}
    return selected, counts


def unique_match(frame: pd.DataFrame, description: str) -> pd.Series:
    if len(frame) != 1:
        raise ValueError(f"Expected exactly one {description}; found {len(frame)}")
    return frame.iloc[0]


def prepare_rows() -> tuple[list[dict], dict]:
    shortlists = parse_shortlist_workbook(INPUT_WORKBOOK)
    selected, shortlist_counts = choose_shortlist(shortlists)
    review = pd.read_csv(PHONOS_REVIEW_MANIFEST, keep_default_na=False)
    baselines = load_baseline_metrics()
    rows: list[dict] = []

    for item in selected:
        direction = item["direction"]
        review_row = unique_match(
            review.loc[
                review["direction"].eq(direction)
                & review["question_no"].eq(item["question_no"])
                & review["source_audio_url"].eq(item["source_audio_url"])
                & review["synthesis_audio_url"].eq(item["synthesis_audio_url"])
            ],
            f"PHONOS audit row for {direction}/{item['question_no']}",
        )
        source_path = Path(review_row["source_original_path"])
        phonos_path = Path(review_row["synthesis_original_path"])
        if published_local_path(item["source_audio_url"]).resolve() != (
            PROJECT_ROOT / "accent" / "phonos_review_samples" / direction
            / Path(item["source_audio_url"]).name
        ).resolve():
            raise ValueError(f"Unexpected source URL layout: {item['source_audio_url']}")
        for label, path in (("source", source_path), ("PHONOS", phonos_path)):
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(f"Missing {label} audio: {path}")

        source_rows = baselines.loc[
            baselines["direction"].eq(direction)
            & baselines["source_wav_path"].eq(str(source_path))
        ]
        seedvc = unique_match(
            source_rows.loc[source_rows["method"].eq("seedvc")],
            f"SeedVC conversion for {direction}/{source_path.name}",
        )
        tvtsyn = unique_match(
            source_rows.loc[source_rows["method"].eq("tvtsyn")],
            f"TVTSyn reconstruction for {direction}/{source_path.name}",
        )
        seedvc_path = Path(seedvc["eval_wav_path"])
        tvtsyn_path = Path(tvtsyn["eval_wav_path"])
        for label, path in (("SeedVC", seedvc_path), ("TVTSyn", tvtsyn_path)):
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(f"Missing {label} audio: {path}")

        source_accent, target_accent = DIRECTION_ACCENTS[direction]
        phonos_target_path = EVAL_ROOT / "speakers" / TARGET_DIR[target_accent] / (
            str(review_row["target_reference"]) + ".wav"
        )
        if not phonos_target_path.is_file():
            raise FileNotFoundError(f"Missing PHONOS target reference: {phonos_target_path}")
        seedvc_target_path = Path(seedvc["target_ref_path"])
        if not seedvc_target_path.is_file():
            raise FileNotFoundError(f"Missing SeedVC target reference: {seedvc_target_path}")

        rows.append(
            {
                "direction": direction,
                "direction_display": DIRECTION_DISPLAY[direction],
                "source_accent": source_accent,
                "target_accent": target_accent,
                "shortlist_question_no": item["question_no"],
                "source_id": str(review_row["source_id"]),
                "source_speaker_id": str(seedvc["source_speaker_id"]),
                "utterance_id": str(seedvc["utterance_id"]),
                "transcript": str(review_row["transcript"]),
                "source_original_path": str(source_path),
                "phonos_original_path": str(phonos_path),
                "seedvc_original_path": str(seedvc_path),
                "tvtsyn_original_path": str(tvtsyn_path),
                "phonos_item_id": str(review_row["selected_item_id"]),
                "phonos_checkpoint": str(review_row["checkpoint"]),
                "phonos_target_ref_id": str(review_row["target_reference"]),
                "phonos_target_ref_path": str(phonos_target_path),
                "phonos_accent_prediction": str(review_row["accent_prediction"]),
                "phonos_target_probability_pct": float(review_row["target_probability_pct"]),
                "phonos_nisqa_mos": float(review_row["nisqa_mos"]),
                "seedvc_item_id": str(seedvc["item_id"]),
                "seedvc_target_ref_id": str(seedvc["target_ref_id"]),
                "seedvc_target_ref_path": str(seedvc_target_path),
                "seedvc_accent_prediction": str(seedvc["accent_pred_label"]),
                "seedvc_recall_tgt_hit": int(seedvc["recall_tgt_hit"]),
                "seedvc_nisqa_mos": float(seedvc["nisqa_mos"]),
                "tvtsyn_item_id": str(tvtsyn["item_id"]),
                "tvtsyn_accent_prediction": str(tvtsyn["accent_pred_label"]),
                "tvtsyn_recall_src_hit": int(tvtsyn["recall_src_hit"]),
                "tvtsyn_nisqa_mos": float(tvtsyn["nisqa_mos"]),
            }
        )
    return rows, shortlist_counts


def publish(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    audio_root = OUTPUT_ROOT / "audio"
    if audio_root.exists():
        shutil.rmtree(audio_root)
    audio_root.mkdir(parents=True)

    wide_rows: list[dict] = []
    long_rows: list[dict] = []
    for direction in SHEET_DIRECTIONS.values():
        direction_rows = [row for row in rows if row["direction"] == direction]
        for sample_number, row in enumerate(direction_rows, start=1):
            sample_id = f"S{sample_number:02d}"
            destination_dir = audio_root / direction
            destination_dir.mkdir(parents=True, exist_ok=True)
            sources = {
                "original": Path(row["source_original_path"]),
                "phonos": Path(row["phonos_original_path"]),
                "seedvc": Path(row["seedvc_original_path"]),
                "tvtsyn_reconstruction": Path(row["tvtsyn_original_path"]),
            }
            published = {}
            for condition, source in sources.items():
                destination = destination_dir / f"{sample_id}__{condition}.wav"
                shutil.copy2(source, destination)
                duration, sample_rate, channels = wav_info(destination)
                relative = destination.relative_to(OUTPUT_ROOT).as_posix()
                published[condition] = {
                    "relative": relative,
                    "url": f"{BASE_URL}/{relative}",
                    "duration": duration,
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "sha256": sha256(destination),
                }
                expected_accent = (
                    row["target_accent"] if condition in {"phonos", "seedvc"}
                    else row["source_accent"]
                )
                long_rows.append(
                    {
                        "sample_group_id": f"{direction}_{sample_id}",
                        "sample_id": sample_id,
                        "direction": direction,
                        "direction_display": row["direction_display"],
                        "condition": condition,
                        "condition_display": AUDIO_LABELS[condition],
                        "expected_accent": expected_accent,
                        "audio": relative,
                        "audio_url": f"{BASE_URL}/{relative}",
                        "duration_sec": duration,
                        "sample_rate_hz": sample_rate,
                        "channels": channels,
                        "sha256": published[condition]["sha256"],
                        "source_id": row["source_id"],
                        "utterance_id": row["utterance_id"],
                    }
                )
            wide = {**row, "sample_group_id": f"{direction}_{sample_id}", "sample_id": sample_id}
            for condition, metadata in published.items():
                wide[f"{condition}_audio"] = metadata["relative"]
                wide[f"{condition}_audio_url"] = metadata["url"]
                wide[f"{condition}_duration_sec"] = metadata["duration"]
                wide[f"{condition}_sha256"] = metadata["sha256"]
            wide_rows.append(wide)
    return pd.DataFrame(wide_rows), pd.DataFrame(long_rows)


def validate(wide: pd.DataFrame, long: pd.DataFrame) -> None:
    expected_directions = list(SHEET_DIRECTIONS.values())
    assert len(wide) == 60
    assert wide.groupby("direction").size().to_dict() == {direction: 10 for direction in expected_directions}
    assert wide.groupby("direction")["source_original_path"].nunique().eq(10).all()
    assert len(long) == 240
    assert long.groupby(["direction", "condition"]).size().eq(10).all()
    assert set(long["condition"]) == set(AUDIO_LABELS)
    assert long["audio"].map(lambda value: (OUTPUT_ROOT / value).is_file()).all()
    assert long["duration_sec"].gt(0).all()
    assert long["sample_rate_hz"].gt(0).all()
    assert long["sha256"].str.len().eq(64).all()
    for row in wide.itertuples(index=False):
        assert Path(row.source_original_path).resolve() == Path(
            getattr(row, "source_original_path")
        ).resolve()
        assert row.seedvc_item_id.startswith(f"seedvc::{row.direction}::")
        assert row.tvtsyn_item_id.startswith(f"tvtsyn::{row.direction}::")


def write_outputs(wide: pd.DataFrame, long: pd.DataFrame, shortlist_counts: dict) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    wide.to_csv(OUTPUT_ROOT / "selection_manifest.csv", index=False)
    long.to_csv(OUTPUT_ROOT / "stimuli_manifest.csv", index=False)
    (OUTPUT_ROOT / "selection_manifest.json").write_text(
        json.dumps(wide.to_dict(orient="records"), indent=2), encoding="utf-8"
    )
    (OUTPUT_ROOT / "stimuli_manifest.json").write_text(
        json.dumps(long.to_dict(orient="records"), indent=2), encoding="utf-8"
    )
    summary = {
        "rng_seed": RNG_SEED,
        "samples_per_direction": SAMPLES_PER_DIRECTION,
        "direction_counts": shortlist_counts,
        "matched_source_groups": len(wide),
        "published_audio_files": len(long),
        "conditions": list(AUDIO_LABELS),
        "selection_policy": (
            "Use all shortlisted PHONOS rows when exactly 10 are available; otherwise "
            "sample 10 without replacement using the fixed RNG seed. Match SeedVC and "
            "TVTSyn reconstruction by direction and exact source_wav_path."
        ),
        "seedvc_target_policy": (
            "Use the target reference already assigned to that source in the full objective evaluation."
        ),
        "source_workbook": str(INPUT_WORKBOOK),
        "phonos_review_manifest": str(PHONOS_REVIEW_MANIFEST),
        "baseline_metric_manifest": str(BASELINE_RESULTS / "metric_manifest_full.csv"),
    }
    (OUTPUT_ROOT / "selection_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (OUTPUT_ROOT / "README.md").write_text(
        """# Matched accent-verification samples

This directory contains the candidate audio set for the revised accent-verification study.
There are 10 matched source groups for each of six conversion directions. Each group contains:

- the original source utterance;
- the manually shortlisted PHONOS conversion;
- a SeedVC conversion of the identical source utterance, using its target reference from the objective evaluation; and
- the TVTSyn reconstruction of the identical source utterance.

`selection_manifest.csv` is the wide provenance and objective-score audit. `stimuli_manifest.csv`
is the long-form, interface-ready list of 240 audio stimuli. JSON equivalents and the fixed
sampling seed are included for reproducibility. The participant-facing trial protocol and order
have not been created yet.

Regenerate this directory with:

```bash
/data/waris/installations/darkstream/bin/python \
  UserStudy/PHONOS-TASLP26/scripts/prepare_accent_new_samples.py
```
""",
        encoding="utf-8",
    )


def main() -> None:
    rows, shortlist_counts = prepare_rows()
    wide, long = publish(rows)
    validate(wide, long)
    write_outputs(wide, long, shortlist_counts)
    print("Shortlist and selected counts:")
    for direction in SHEET_DIRECTIONS.values():
        counts = shortlist_counts[direction]
        print(f"  {direction}: {counts['shortlisted']} -> {counts['selected']}")
    print("\nPublished condition counts:")
    print(long.groupby(["direction", "condition"]).size().to_string())
    print(f"\nWrote {len(wide)} matched groups and {len(long)} WAV files to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
