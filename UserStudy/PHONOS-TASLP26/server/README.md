# PHONOS-TASLP26 Response API

This FastAPI service stores responses for both current perceptual studies in one Neon PostgreSQL database:

- `phonos_taslp26_accent_multidimensional` (`accent_new`)
- `phonos_taslp26_voice_similarity_abx` (`voice_similarity`)

Each submission is saved both as the original JSON payload and as 60 queryable rows in `trial_responses`. Browser-generated submission IDs make retries idempotent: retrying the same completed payload returns success without inserting duplicate rows.

## Local Setup

```bash
cd /data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26/server
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 127.0.0.1 --port 8787
```

The default `.env` uses SQLite for local development. Check it with:

```bash
curl http://127.0.0.1:8787/health
```

Do not use the SQLite configuration on Vercel; its function filesystem is not durable storage.

## Create the Neon Database

1. Create one Neon project and database.
2. Copy both connection strings from the Neon dashboard:
   - pooled URL for the deployed API runtime;
   - direct/unpooled URL for schema migrations.
3. From this directory, run the migration using the direct URL:

```bash
source .venv/bin/activate
export DATABASE_URL_UNPOOLED='postgresql://USER:PASSWORD@DIRECT_HOST/DBNAME?sslmode=require'
python migrate.py
```

Keep connection strings and `ADMIN_TOKEN` out of Git. Runtime requests should use the pooled Neon hostname, which normally contains `-pooler`.

## Deploy the API to Vercel

Deploy this `server` directory as the Vercel project's root. `app.py` is the FastAPI entrypoint and `.python-version` selects Python 3.12.

Install and authenticate the CLI if needed:

```bash
npm install --global vercel
vercel login
cd /data/waris/code/anonymousis23.github.io/UserStudy/PHONOS-TASLP26/server
vercel link
```

Add these production environment variables in the Vercel dashboard or with `vercel env add NAME production`:

```text
DATABASE_URL=<Neon pooled connection string>
AUTO_CREATE_SCHEMA=0
ALLOWED_ORIGINS=https://anonymousis23.github.io
ALLOWED_STUDY_IDS=phonos_taslp26_accent_multidimensional,phonos_taslp26_voice_similarity_abx
ADMIN_TOKEN=<long random secret>
```

Then deploy:

```bash
vercel --prod
```

The resulting endpoints are:

```text
https://YOUR-PROJECT.vercel.app/health
https://YOUR-PROJECT.vercel.app/api/submissions
```

## Verify Before Launch

The read-only smoke check does not write participant data:

```bash
python smoke_deployment.py https://YOUR-PROJECT.vercel.app
```

The full smoke test writes two clearly tagged test submissions, one for each study, and verifies the first insert, an idempotent retry, and the status endpoint:

```bash
python smoke_deployment.py https://YOUR-PROJECT.vercel.app --write
```

After this passes, update both study manifests in one command:

```bash
python ../scripts/set_managed_response_api.py https://YOUR-PROJECT.vercel.app
```

Commit and push the two manifest changes so GitHub Pages serves the permanent endpoint. The existing ngrok URLs are intentionally left in place until this step.

## Reliability Behavior

Both study pages load `shared/submission.js`. On submission it:

1. assigns a stable client submission ID;
2. persists the exact completed payload in browser storage;
3. retries transient failures with backoff;
4. requires the API to confirm the same ID;
5. removes the pending payload only after confirmed storage.

If all attempts fail, the participant remains on the completion page and can press **Submit** again. The same payload and ID are reused, so a response lost after the database commit does not produce a duplicate.

## Exports

Administrative endpoints fail closed unless `ADMIN_TOKEN` is configured. Prefer the header form so the token does not appear in URLs or browser history:

```bash
export API_URL='https://YOUR-PROJECT.vercel.app'
export ADMIN_TOKEN='your-secret'
curl -H "X-Admin-Token: $ADMIN_TOKEN" "$API_URL/api/export/submissions.csv" -o submissions.csv
curl -H "X-Admin-Token: $ADMIN_TOKEN" "$API_URL/api/export/trial_responses.csv" -o trial_responses.csv
curl -H "X-Admin-Token: $ADMIN_TOKEN" "$API_URL/api/export/raw.jsonl" -o raw.jsonl
```

The API keeps Prolific `PROLIFIC_PID`, `STUDY_ID`, and `SESSION_ID` separate from the internal study ID. Accent responses use `naturalness_choice`, `primary_accent`, `secondary_accent`, and `secondary_influence`. Voice-similarity responses use `accent_choice`/`abx_choice` and `similarity_rating`. Full hidden trial metadata remains available in the raw JSON export.
