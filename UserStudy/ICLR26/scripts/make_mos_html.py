#!/usr/bin/env python3
import argparse
import html
import random
from pathlib import Path
from urllib.parse import quote

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

def url_join(base: str, rel: Path) -> str:
    base = base.rstrip("/") + "/"
    parts = [quote(p) for p in rel.as_posix().split("/") if p]
    return base + "/".join(parts)

def find_wavs(samples_root: Path):
    """Return list of (model, rel_path, stem) where rel_path is relative to samples_root."""
    wavs = []

    # 1) src/*
    src_dir = samples_root / "src"
    if src_dir.exists():
        src_files = sorted(src_dir.rglob("*"))
        src_file_stems = [(p.stem).split("_")[0]+"_"+(p.stem).split("_")[1] for p in src_files if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
        src_file_stems = set(src_file_stems)
        count = 0
        for p in sorted(src_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS and p.stem in src_file_stems:
                rel = p.relative_to(samples_root)
                wavs.append(("src", rel, p.stem))
                count += 1
                if count == 15:
                    break

    # 2) vc/<model>/*
    vc_dir = samples_root / "vc"
    if vc_dir.exists():
        for model_dir in sorted(vc_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            model = model_dir.name
            for p in sorted(model_dir.rglob("*")):
                if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                    rel = p.relative_to(samples_root)
                    wavs.append((model, rel, p.stem))
    return wavs

def write_html(out_html: Path, wav_list: list, set_size: int, append_raw: bool):
    out_html.parent.mkdir(parents=True, exist_ok=True)
    with out_html.open("w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MOS Test</title>
<style>
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
h1 { margin: 0 0 12px; }
h2 { margin: 24px 0 8px; }
table.tests { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
.tests td, .tests th { border: 1px solid #ddd; padding: 8px; vertical-align: middle; }
.tests tr:nth-child(even){ background: #fafafa; }
audio { width: 260px; }
.center { text-align: center; }
td:first-child, th:first-child { white-space: nowrap; }
.note { background: #fff9c4; padding: 8px 12px; border-radius: 8px; }
</style>
</head>
<body>
<h1>Mean Opinion Score (MOS) Test</h1>
<p class="note">For each question, listen to the clip and rate the overall quality (5=Excellent, 1=Bad). The first row reminds the scale.</p>
""")
        num_sets = len(wav_list) // set_size
        for i in range(num_sets):
            f.write(f'<h2>Set {i+1}</h2>')
            f.write('<table class="tests"><tbody>')
            # Scale header row
            f.write("		<tr>")
            f.write("			<td></td>")
            f.write("			<td>(Level of distortion)</td>")
            f.write("			<td>Imperceptible</td>")
            f.write("			<td>Just perceptible, but not annoying</td>")
            f.write("			<td>Perceptible and slightly annoying</td>")
            f.write("			<td>Annoying, but not objectionable</td>")
            f.write("			<td>Very annoying and objectionable</td>")
            f.write("		</tr>")
            # Column header row
            f.write("		<tr>")
            f.write("			<td><strong>Q ID</strong></td>")
            f.write("			<td><strong>&nbsp; &nbsp;Clip &nbsp;&nbsp;</strong></td>")
            f.write("			<td><strong>Excellent</strong></td>")
            f.write("			<td><strong>Good</strong></td>")
            f.write("			<td><strong>Fair</strong></td>")
            f.write("			<td><strong>Poor</strong></td>")
            f.write("			<td><strong>Bad</strong></td>")
            f.write("		</tr>")

            for j in range(set_size):
                index = i * set_size + j
                row = wav_list[index]
                wav_id = row["id"]
                wav_url = row["wav_fpath"]
                if append_raw and "?raw=True" not in wav_url:
                    connector = "&" if "?" in wav_url else "?"
                    wav_url = wav_url + f"{connector}raw=True"

                f.write("		<tr>")
                f.write(f"			<td>Q{index+1}</td>")

                f.write("""			<td>
				<audio controls preload="none">""")
                f.write(f'					<source preload="none" src="{html.escape(wav_url)}" type="audio/wav" />')
                f.write("				</audio></td>")

                # 5..1 radio buttons
                for val in (5, 4, 3, 2, 1):
                    f.write(f'			<td class="center"><input name="{html.escape(wav_id)}" type="radio" value="{val}" /></td>')

                f.write("		</tr>")
            f.write("	</tbody></table>")
        f.write("</body></html>")

def main():
    parser = argparse.ArgumentParser(description="Build MOS HTML from Samples/Verifiability layout.")
    parser.add_argument("--samples_root", type=Path, default=Path("../Samples/Verifiability2"),
                        help="Local path to Samples/Verifiability")
    parser.add_argument("--public_base", type=str, required=True,
                        help="Base URL that maps to samples_root on GitHub Pages, e.g., "
                             "'https://anonymousis23.github.io/UserStudy/ICLR26/Samples/Verifiability2/'")
    parser.add_argument("--out_dir", type=Path, default=Path("."),
                        help="Directory where index.html will be written")
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument("--set_size", type=int, default=5)
    parser.add_argument("--append_raw", action="store_true",
                        help="Append '?raw=True' to audio URLs (useful for non-Pages hosting).")
    args = parser.parse_args()

    # Discover files
    triples = find_wavs(args.samples_root)  # (model, relpath, stem)
    if not triples:
        raise SystemExit(f"No audio found under {args.samples_root}")

    # Build wav_list entries
    wav_list = []
    for model, rel, stem in triples:
        wav_id = f"MOS_{model}_{stem}"
        wav_url = url_join(args.public_base.rstrip("/"), rel)
        wav_list.append({"id": wav_id, "wav_fpath": wav_url, "model": model, "stem": stem})

    # Shuffle deterministically
    random.seed(args.seed)
    random.shuffle(wav_list)

    # Write HTML
    out_html = args.out_dir / "index.html"
    write_html(out_html, wav_list, set_size=args.set_size, append_raw=args.append_raw)

    # Console summary
    n = len(wav_list)
    print(f"Total clips: {n} | Sets of {args.set_size}: {n // args.set_size}")
    print(f"Wrote: {out_html}")

if __name__ == "__main__":
    main()