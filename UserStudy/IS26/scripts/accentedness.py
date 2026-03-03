#!/usr/bin/env python3
"""
Generate MOS HTML tables for wavs hosted on GitHub Pages.

Expected structure:
  IS26/samples/accentedness/<accent>/<speaker>/<utter_id>.wav

Output:
  mos_accentedness.html (by default)
"""

from __future__ import annotations
import os
import re
import json
import glob
import urllib.request
from dataclasses import dataclass
from typing import List, Tuple
from collections import defaultdict
from pathlib import Path
import random

# ----------------------------- CONFIG -----------------------------

GHPAGES_BASE = "https://anonymousis23.github.io/UserStudy/IS26/samples/accentedness"

# If you want to list files from GitHub repo (recommended):
GITHUB_OWNER = "anonymousis23"
GITHUB_REPO = "UserStudy"
GITHUB_BRANCH = "main"  # change if needed

# Path inside the repo where wavs live:
REPO_SUBDIR = "IS26/samples/accentedness"

# If you want local glob instead, set LOCAL_ROOT to your local folder path:
# e.g., LOCAL_ROOT="/path/to/UserStudy/IS26/samples/accentedness"
LOCAL_ROOT = "/data/waris/code/anonymousis23.github.io/UserStudy/IS26/samples/accentedness"  # set to a string to use local glob mode

# If you *must* enforce 80:
EXPECTED_COUNT = 90

# -----------------------------------------------------------------


@dataclass(frozen=True)
class Clip:
    accent: str
    speaker: str
    utter_id: str
    url: str  # GitHub Pages URL to wav


def _http_get_json(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def _slug(s: str) -> str:
    """
    Make a safe token for HTML input names.
    Keep letters/digits/_- only; convert others to underscore.
    """
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-]", "_", s)
    return s


def list_clips_via_github_api() -> List[Clip]:
    """
    Recursively list wav files via GitHub tree API, then map them to GitHub Pages URLs.
    """
    # 1) Get the branch ref -> commit -> tree sha
    ref_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/refs/heads/{GITHUB_BRANCH}"
    ref = _http_get_json(ref_url, headers={"Accept": "application/vnd.github+json"})
    commit_sha = ref["object"]["sha"]

    commit_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/commits/{commit_sha}"
    commit = _http_get_json(commit_url, headers={"Accept": "application/vnd.github+json"})
    tree_sha = commit["tree"]["sha"]

    # 2) Fetch full recursive tree
    tree_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/{tree_sha}?recursive=1"
    tree = _http_get_json(tree_url, headers={"Accept": "application/vnd.github+json"})

    clips: List[Clip] = []
    prefix = REPO_SUBDIR.rstrip("/") + "/"

    for obj in tree.get("tree", []):
        if obj.get("type") != "blob":
            continue
        path = obj.get("path", "")
        if not path.startswith(prefix):
            continue
        if not path.lower().endswith(".wav"):
            continue

        # path example:
        # IS26/samples/accentedness/american/spk123/1.wav
        rel = path[len(prefix):]  # american/spk123/1.wav
        parts = rel.split("/")
        if len(parts) != 3:
            # Skip unexpected layouts
            continue

        accent, speaker, fname = parts
        utter_id = os.path.splitext(fname)[0]

        url = f"{GHPAGES_BASE}/{accent}/{speaker}/{fname}"
        clips.append(Clip(accent=accent, speaker=speaker, utter_id=utter_id, url=url))

    # Deterministic ordering
    clips.sort(key=lambda c: (c.accent.lower(), c.speaker.lower(), c.utter_id.lower()))
    return clips


# def list_clips_via_local_glob(local_root: str) -> List[Clip]:
#     """
#     List wav files locally with glob and map to GitHub Pages URLs with same relative path.
#     """
#     pattern = os.path.join(local_root, "*", "*", "*.wav")
#     paths = glob.glob(pattern)
#     clips: List[Clip] = []

#     for p in sorted(paths):
#         rel = os.path.relpath(p, local_root)  # accent/speaker/file.wav
#         parts = rel.split(os.sep)
#         if len(parts) != 3:
#             continue
#         accent, speaker, fname = parts
#         utter_id = os.path.splitext(fname)[0]
#         url = f"{GHPAGES_BASE}/{accent}/{speaker}/{fname}"
#         clips.append(Clip(accent=accent, speaker=speaker, utter_id=utter_id, url=url))

#     clips.sort(key=lambda c: (c.accent.lower(), c.speaker.lower(), c.utter_id.lower()))
#     return clips
  
def list_clips_via_local_glob(
    local_root: str,
    samples_per_accent: int = 15,
    seed: int = 1337,
    strict: bool = True,
) -> List[Clip]:
    """
    List wav files locally, then for each accent randomly sample `samples_per_accent` files.
    Map to GitHub Pages URLs with same relative path.

    strict=True  -> error if an accent has < samples_per_accent files
    strict=False -> take all available if fewer than requested
    """
    pattern = os.path.join(local_root, "*", "*", "*.wav")
    paths = glob.glob(pattern)

    # group filepaths by accent
    by_accent = defaultdict(list)
    for p in paths:
        rel = os.path.relpath(p, local_root)  # accent/speaker/file.wav
        parts = rel.split(os.sep)
        if len(parts) != 3:
            continue
        accent = parts[0]
        by_accent[accent].append(p)

    rng = random.Random(seed)

    # sample per accent
    selected_paths = []
    for accent, accent_paths in sorted(by_accent.items(), key=lambda x: x[0].lower()):
        accent_paths = sorted(accent_paths)
        if strict and len(accent_paths) < samples_per_accent:
            raise RuntimeError(
                f"Accent '{accent}' has only {len(accent_paths)} files, "
                f"but samples_per_accent={samples_per_accent}."
            )
        k = min(samples_per_accent, len(accent_paths))
        selected_paths.extend(rng.sample(accent_paths, k))

    # build Clip objects
    clips: List[Clip] = []
    for p in sorted(selected_paths):
        rel = os.path.relpath(p, local_root)  # accent/speaker/file.wav
        accent, speaker, fname = rel.split(os.sep)
        utter_id = os.path.splitext(fname)[0]
        url = f"{GHPAGES_BASE}/{accent}/{speaker}/{fname}"
        clips.append(Clip(accent=accent, speaker=speaker, utter_id=utter_id, url=url))

    clips.sort(key=lambda c: (c.accent.lower(), c.speaker.lower(), c.utter_id.lower()))
    return clips


def render_set_table(set_idx_1based: int, set_clips: List[Clip], q_start_1based: int) -> str:
    """
    Render one 5-item MOS table (or fewer if last chunk).
    """
    header = f"""
<h2>Set {set_idx_1based}</h2>
<table class="tests">
  <tbody>
    <tr>
      <td><strong>Q ID</strong></td>
      <td><strong>&nbsp; &nbsp;Clip &nbsp;&nbsp;</strong></td>
      <td><strong>No foreign accent</strong></td>
      <td><strong>|</strong></td>
      <td><strong>Some foreign accent</strong></td>
      <td><strong>|</strong></td>
      <td><strong>Quite a bit foreign accent</strong></td>
      <td><strong>|</strong></td>
      <td><strong>Strong foreign accent</strong></td>
      <td><strong>|</strong></td>
      <td><strong>Very strong foreign accent</strong></td>
    </tr>
""".strip()

    rows = []
    for i, c in enumerate(set_clips):
        qid = q_start_1based + i  # global Q numbering (Q1..Q80)
        name = f"ACC_{_slug(c.accent)}_{_slug(c.speaker)}_{_slug(c.utter_id)}"
        row = f"""
    <tr>
      <td>Q{qid}</td>
      <td>
        <audio controls="controls" preload="none">
          <source preload="none" src="{c.url}" type="audio/wav" />
        </audio>
      </td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="1" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="2" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="3" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="4" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="5" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="6" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="7" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="8" /></td>
      <td style="text-align: center;"><input name="{name}" type="radio" value="9" /></td>
    </tr>
""".rstrip()
        rows.append(row)

    footer = """
  </tbody>
</table>
""".strip()

    return "\n".join([header] + rows + [footer])


def render_full_html(clips: List[Clip], per_set: int = 5) -> str:
    """
    Render the full HTML document with 16 sets (for 80 clips at 5 per set).
    """
    # chunk into sets
    sets: List[List[Clip]] = [clips[i:i + per_set] for i in range(0, len(clips), per_set)]

    tables = []
    q = 1
    for sidx, sclips in enumerate(sets, start=1):
        tables.append(render_set_table(sidx, sclips, q_start_1based=q))
        q += len(sclips)

    body = "\n\n".join(tables)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Accentedness Study</title>
  <style>
    table.tests {{
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 24px;
    }}
    table.tests td {{
      border: 1px solid #ddd;
      padding: 8px;
      vertical-align: middle;
    }}
    table.tests tr:nth-child(even) {{
      background: #fafafa;
    }}
    audio {{
      width: 280px;
    }}
    h2 {{
      margin-top: 28px;
    }}
  </style>
</head>
<body>

<h2><strong>Please rate the audio quality of the following clips:</strong></h2>

{body}

</body>
</html>
"""
    return html


def main(out_html: str = "accentedness.html"):
    if LOCAL_ROOT:
        clips = list_clips_via_local_glob(LOCAL_ROOT)
    else:
        clips = list_clips_via_github_api()

    if EXPECTED_COUNT is not None and len(clips) != EXPECTED_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_COUNT} wavs, but found {len(clips)}. "
                           f"Check branch/path/config. (REPO_SUBDIR={REPO_SUBDIR})")
        
    
    import random
    random.seed(42)  # for reproducibility
    random.shuffle(clips)

    html = render_full_html(clips, per_set=5)

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote: {out_html}  (clips={len(clips)}, sets={len(clips)//5})")


if __name__ == "__main__":
    main()