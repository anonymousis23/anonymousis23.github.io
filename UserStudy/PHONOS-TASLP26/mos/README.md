# PHONOS MOS Listening Study

Static MOS study interface for PHONOS-TASLP26. Participants rate one audio clip at a time on a 1-5 MOS quality scale. The study has 60 randomized trials: 15 `original`, 15 `PHONOS`, 15 `seedvc`, and 15 `TVTSyn`.

## Files

- `index.html`: study page.
- `assets/app.js`: pagination, cooldown, validation, local JSON backup, and response submission.
- `assets/style.css`: responsive UI styling.
- `trials.json`: study configuration and randomized trial order.
- `trials.csv`: spreadsheet-friendly copy of the trial order.
- `audio/`: placeholder WAVs. Replace these with the final stimuli or update `trials.json`/`trials.csv`.

The MOS reference samples are loaded from `../../../commons/reference_samples_mos/Reference/*.wav` using relative paths instead of GitHub `blob` URLs.

## Response API

This study can use the shared backend in `../server`. Put the public endpoint in `trials.json`:

```json
"response_api_url": "https://YOUR-TUNNEL.ngrok-free.app/api/submissions"
```

The frontend also downloads a local JSON backup after submission.

## Study Design

- 5 trials per page.
- 12 pages total.
- 12-second cooldown after every 15 rated samples.
- Fixed randomized order seed: `260813`.

When final audio is ready, keep the filenames in `audio/` if possible. If filenames change, update both `trials.json` and `trials.csv` so the stored order remains correct.
