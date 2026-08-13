# PHONOS TASLP26 Accent Verification Study

Static GitHub Pages listening interfaces for accent verification.

## Interfaces

- `indian/`: American vs Indian accent verification
- `spanish/`: American vs Spanish-accented English verification
- `british/`: American vs British accent verification

Each interface shows 5 samples per page. After every 3 pages, i.e. after 15 rated samples, participants see a 12 second cooldown before continuing.

## Trial Manifests

Each study folder contains:

- `trials.json`: loaded dynamically by the interface
- `trials.csv`: flat copy of the randomized order for analysis
- `audio/`: placeholder wavs named by randomized question ID and condition

The randomized order is stored in both `trials.json` and `trials.csv`. The audio filenames also encode the displayed question number and condition, for example:

```text
Q001__phonos_ind2ame__src05__placeholder.wav
```

Important columns:

- `qid`: displayed question ID
- `display_index`: randomized presentation order, 1 to 60
- `page`: 5-sample page number
- `cooldown_block`: 15-sample block number
- `condition`: source/system condition
- `expected_accent`: hidden ground-truth accent label for analysis
- `audio`: relative audio path loaded by the page

## Replacing Placeholder Audio

Replace the placeholder wav files in each `audio/` folder with real samples. The safest option is to keep the same filenames so the manifests do not need to change.

If you prefer different filenames, update the `audio` field in both `trials.json` and `trials.csv`.



## Recommended Response Capture Backend

A small FastAPI backend is included in `server/`. It is more reliable than Google Apps Script for full-study JSON submissions and stores both raw submissions and normalized per-trial rows.

Quick start:

```bash
cd /data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26/accent/server
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 0.0.0.0 --port 8787
```

Expose it publicly with a tunnel such as ngrok:

```bash
ngrok http 8787
```

Then put the HTTPS endpoint plus `/api/submissions` into each study config:

```json
"response_api_url": "https://YOUR-TUNNEL.ngrok-free.app/api/submissions"
```

Set this separately in:

- `indian/trials.json`
- `spanish/trials.json`
- `british/trials.json`

The frontend uses `response_api_url` first. If it is blank or still a `TODO_...` placeholder, it falls back to `apps_script_webapp_url` if that is a real URL. Either way, it downloads a local JSON backup for the participant.

After the study, export CSV files from the backend:

```bash
curl "http://127.0.0.1:8787/api/export/submissions.csv" -o submissions.csv
curl "http://127.0.0.1:8787/api/export/trial_responses.csv" -o trial_responses.csv
curl "http://127.0.0.1:8787/api/export/raw.jsonl" -o raw.jsonl
```

## Per-Study Submission URLs

Each study has its own endpoint placeholders in its `trials.json` file:

```json
"response_api_url": "TODO_INDIAN_RESPONSE_API_URL",
"apps_script_webapp_url": "TODO_INDIAN_GOOGLE_APPS_SCRIPT_WEBAPP_URL",
"prolific_completion_url": "TODO_INDIAN_PROLIFIC_COMPLETION_URL"
```

Set these separately for:

- `indian/trials.json`
- `spanish/trials.json`
- `british/trials.json`

The shared interface reads the URLs dynamically from the currently loaded `trials.json`, so each study can submit to a different response API or Google Apps Script and redirect to a different Prolific completion URL. Endpoint values are used only if they start with `http://` or `https://`; blank values or `TODO_...` placeholders are safely ignored, and the interface still downloads a local JSON response file as a fallback.

## Responses

The current static interface downloads a JSON response file at the end of the study. It also keeps a local browser draft while the participant is working.

If you want Google Sheets submission, set `APPS_SCRIPT_WEBAPP_URL` near the top of `assets/app.js` to the Apps Script web app endpoint. The JSON download remains as a fallback.
