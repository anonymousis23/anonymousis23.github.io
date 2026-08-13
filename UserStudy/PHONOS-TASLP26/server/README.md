# PHONOS-TASLP26 Response API

Small FastAPI backend for collecting PHONOS perceptual-study responses. The same server can be used by the accent verification studies and the MOS study. It stores each submission as one raw JSON payload and also expands every trial into a CSV-friendly `trial_responses` table.

SQLite is the default and is enough for a small study. PostgreSQL is supported by setting `DATABASE_URL`.

## Setup

```bash
cd /data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26/server
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

## Run Locally

```bash
uvicorn app:app --host 0.0.0.0 --port 8787
```

Health check:

```bash
curl http://127.0.0.1:8787/health
```

Submission endpoint:

```text
http://127.0.0.1:8787/api/submissions
```

Set this URL in each study manifest as `response_api_url`. The payload includes `study_id` and `task_type`, so accent and MOS studies can share the same endpoint.

## Use PostgreSQL Instead of SQLite

Create a database and set this in `.env`:

```bash
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME
```

Then restart the server. Tables are created automatically.

## Expose Publicly

Use a tunnel such as ngrok or Cloudflare Tunnel. Example with ngrok:

```bash
ngrok http 8787
```

Then copy the HTTPS forwarding URL and append `/api/submissions`, for example:

```text
https://YOUR-TUNNEL.ngrok-free.app/api/submissions
```

Put that URL in each study's `trials.json` as `response_api_url`.

## Exports

If `ADMIN_TOKEN` is empty in `.env`, export endpoints are open locally. If you set `ADMIN_TOKEN`, pass `?token=YOUR_TOKEN`.

```bash
curl "http://127.0.0.1:8787/api/export/submissions.csv" -o submissions.csv
curl "http://127.0.0.1:8787/api/export/trial_responses.csv" -o trial_responses.csv
curl "http://127.0.0.1:8787/api/export/raw.jsonl" -o raw.jsonl
```

With a token:

```bash
curl "http://127.0.0.1:8787/api/export/trial_responses.csv?token=YOUR_TOKEN" -o trial_responses.csv
```

MOS rows use `mos_rating`, `mos_label`, and `distortion_label`. Accent rows use `accent_choice` and `confidence`. Raw JSON always contains the full original browser payload.
