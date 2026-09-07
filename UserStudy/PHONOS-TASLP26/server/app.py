from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./responses.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()
AUTO_CREATE_SCHEMA = os.getenv(
    "AUTO_CREATE_SCHEMA", "1" if DATABASE_URL.startswith("sqlite") else "0"
).lower() in {"1", "true", "yes"}
DEFAULT_STUDY_IDS = {
    "phonos_taslp26_accent_british",
    "phonos_taslp26_accent_indian",
    "phonos_taslp26_accent_multidimensional",
    "phonos_taslp26_accent_qualification",
    "phonos_taslp26_accent_spanish",
    "phonos_taslp26_mos",
    "phonos_taslp26_voice_similarity_abx",
}
ALLOWED_STUDY_IDS = {
    value.strip()
    for value in os.getenv("ALLOWED_STUDY_IDS", ",".join(sorted(DEFAULT_STUDY_IDS))).split(",")
    if value.strip()
}
QUALIFICATION_STUDY_ID = "phonos_taslp26_accent_qualification"
QUALIFICATION_TOTAL = 12
STRICT_STUDY_IDS = {
    "phonos_taslp26_accent_multidimensional",
    QUALIFICATION_STUDY_ID,
    "phonos_taslp26_voice_similarity_abx",
}


def load_qualification_answer_key() -> dict[str, str]:
    raw = os.getenv("QUALIFICATION_ANSWER_KEY", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("QUALIFICATION_ANSWER_KEY must be a JSON object") from error
    accents = {"american", "british", "indian", "spanish"}
    normalized = {str(key): str(value).lower() for key, value in parsed.items()}
    if len(normalized) != QUALIFICATION_TOTAL or set(normalized.values()) != accents:
        raise RuntimeError(
            "QUALIFICATION_ANSWER_KEY must contain 12 items covering all four accents"
        )
    return normalized


QUALIFICATION_ANSWER_KEY = load_qualification_answer_key()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_options = {"connect_args": connect_args, "future": True, "pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    engine_options["pool_recycle"] = 300
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True)
    study_id = Column(String, index=True, nullable=False)
    task_type = Column(String, index=True, default="")
    target_accent = Column(String, index=True, default="")
    form_id = Column(String, index=True, default="")
    form_assignment_basis = Column(String, default="")
    prolific_pid = Column(String, index=True, default="")
    prolific_study_id = Column(String, index=True, default="")
    prolific_session_id = Column(String, index=True, default="")
    participant_id = Column(String, index=True, default="")
    page_url = Column(Text, default="")
    user_agent = Column(Text, default="")
    started_at_ms = Column(Float, nullable=True)
    submitted_at_ms = Column(Float, nullable=True)
    payload_sha256 = Column(String(64), default="")
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    raw_payload = Column(JSON, nullable=False)


class TrialResponse(Base):
    __tablename__ = "trial_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(String, index=True, nullable=False)
    study_id = Column(String, index=True, nullable=False)
    task_type = Column(String, index=True, default="")
    qid = Column(String, index=True, default="")
    display_index = Column(Integer, nullable=True)
    page = Column(Integer, nullable=True)
    condition = Column(String, index=True, default="")
    condition_label = Column(Text, default="")
    expected_accent = Column(String, index=True, default="")
    audio = Column(Text, default="")
    source_index = Column(Integer, nullable=True)
    accent_choice = Column(String, index=True, default="")
    confidence = Column(Integer, nullable=True)
    naturalness_choice = Column(String, index=True, default="")
    naturalness_correct = Column(Integer, nullable=True)
    primary_accent = Column(String, index=True, default="")
    primary_accent_correct = Column(Integer, nullable=True)
    secondary_accent = Column(String, index=True, default="")
    secondary_influence = Column(Integer, nullable=True)
    playback_count = Column(Integer, nullable=True)
    similarity_rating = Column(Integer, nullable=True)
    mos_rating = Column(Integer, nullable=True)
    mos_label = Column(String, index=True, default="")
    distortion_label = Column(Text, default="")
    response_ts_ms = Column(Float, nullable=True)


class SubmissionPayload(BaseModel):
    submission_id: str | None = Field(default="", max_length=64)
    study_id: str = Field(..., min_length=1)
    task_type: str | None = ""
    title: str | None = ""
    target_accent: str | None = ""
    form_id: str | None = ""
    form_assignment_basis: str | None = ""
    randomized_order_seed: int | None = None
    page_size: int | None = None
    cooldown_seconds: int | None = None
    participant: dict[str, Any] = Field(default_factory=dict)
    post_survey: dict[str, Any] = Field(default_factory=dict)
    started_at: float | None = None
    submitted_at: float | None = None
    user_agent: str | None = ""
    page_url: str | None = ""
    rows: list[dict[str, Any]] = Field(default_factory=list)


def migrate_database() -> None:
    Base.metadata.create_all(engine)
    additions = {
        "submissions": {
            "prolific_study_id": "VARCHAR DEFAULT ''",
            "prolific_session_id": "VARCHAR DEFAULT ''",
            "form_id": "VARCHAR DEFAULT ''",
            "form_assignment_basis": "VARCHAR DEFAULT ''",
            "payload_sha256": "VARCHAR(64) DEFAULT ''",
        },
        "trial_responses": {
            "similarity_rating": "INTEGER",
            "naturalness_choice": "VARCHAR DEFAULT ''",
            "naturalness_correct": "INTEGER",
            "primary_accent": "VARCHAR DEFAULT ''",
            "primary_accent_correct": "INTEGER",
            "secondary_accent": "VARCHAR DEFAULT ''",
            "secondary_influence": "INTEGER",
            "playback_count": "INTEGER",
        },
    }
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {
                column["name"] for column in inspect(connection).get_columns(table_name)
            }
            for column_name, sql_type in columns.items():
                if column_name in existing:
                    continue
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}"
                )
                existing.add(column_name)


def init_db() -> None:
    if AUTO_CREATE_SCHEMA:
        migrate_database()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(token: str | None = Query(default=None), x_admin_token: str | None = Header(default=None)) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Administrative exports are disabled")
    supplied = token or x_admin_token or ""
    if not secrets.compare_digest(supplied, ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid admin token")


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def payload_dict(payload: SubmissionPayload) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return payload.dict()


def payload_sha256(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def qualification_result(data: dict[str, Any]) -> dict[str, Any] | None:
    if data.get("study_id") != QUALIFICATION_STUDY_ID:
        return None
    choices = {
        str(row.get("qid") or ""): str(
            row.get("accent_choice") or row.get("primary_accent") or ""
        ).lower()
        for row in data.get("rows", [])
    }
    score = sum(
        choices.get(qid) == expected
        for qid, expected in QUALIFICATION_ANSWER_KEY.items()
    )
    return {
        "qualification_score": score,
        "qualification_total": QUALIFICATION_TOTAL,
        "qualification_passed": score == QUALIFICATION_TOTAL,
    }


def normalized_submission_id(value: str | None) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", candidate):
        raise HTTPException(status_code=422, detail="Invalid submission_id")
    return candidate


def validate_submission(payload: SubmissionPayload) -> None:
    if payload.study_id not in ALLOWED_STUDY_IDS:
        raise HTTPException(status_code=422, detail="Unknown study_id")
    if payload.study_id not in STRICT_STUDY_IDS:
        return

    accents = {"american", "british", "indian", "spanish"}
    qids = [str(row.get("qid") or "") for row in payload.rows]
    if any(not qid for qid in qids) or len(qids) != len(set(qids)):
        raise HTTPException(status_code=422, detail="Trial qids must be present and unique")

    if payload.study_id == QUALIFICATION_STUDY_ID:
        if len(payload.rows) != QUALIFICATION_TOTAL:
            raise HTTPException(status_code=422, detail="Qualification requires exactly 12 trial rows")
        if payload.form_id not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=422, detail="FORM_ID must be A, B, C, or D")
        if len(QUALIFICATION_ANSWER_KEY) != QUALIFICATION_TOTAL:
            raise HTTPException(status_code=503, detail="Qualification scoring is not configured")
        if set(qids) != set(QUALIFICATION_ANSWER_KEY):
            raise HTTPException(status_code=422, detail="Qualification trial identifiers do not match")
        for row in payload.rows:
            choice = str(row.get("accent_choice") or row.get("primary_accent") or "")
            if choice not in accents:
                raise HTTPException(status_code=422, detail="Invalid qualification accent response")
            if (as_int(row.get("playback_count")) or 0) < 1:
                raise HTTPException(status_code=422, detail="Every qualification recording must be played")
        return

    if len(payload.rows) != 60:
        raise HTTPException(status_code=422, detail="This study requires exactly 60 trial rows")

    if payload.study_id == "phonos_taslp26_accent_multidimensional":
        if payload.form_id not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=422, detail="FORM_ID must be A, B, C, or D")
        for row in payload.rows:
            naturalness = str(row.get("naturalness_choice") or "")
            primary = str(row.get("primary_accent") or "")
            secondary = str(row.get("secondary_accent") or "")
            influence = as_int(row.get("secondary_influence"))
            if naturalness not in {"natural", "synthetic", "unsure"}:
                raise HTTPException(status_code=422, detail="Invalid naturalness response")
            if primary not in accents:
                raise HTTPException(status_code=422, detail="Invalid primary accent")
            if secondary not in accents | {"none"} or secondary == primary:
                raise HTTPException(status_code=422, detail="Invalid secondary accent")
            if secondary != "none" and influence not in {1, 2, 3, 4, 5}:
                raise HTTPException(status_code=422, detail="Invalid secondary accent influence")
    elif payload.study_id == "phonos_taslp26_voice_similarity_abx":
        for row in payload.rows:
            choice = str(row.get("abx_choice") or row.get("accent_choice") or "")
            similarity = as_int(row.get("similarity_rating"))
            if choice not in {"A", "B"} or similarity not in {1, 2, 3, 4, 5}:
                raise HTTPException(status_code=422, detail="Invalid voice-similarity response")


app = FastAPI(title="PHONOS Listening Study Response API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"ok": "true", "database": engine.dialect.name}


def duplicate_response(db: Session, submission: Submission, digest: str) -> JSONResponse:
    if submission.payload_sha256 and submission.payload_sha256 != digest:
        raise HTTPException(status_code=409, detail="submission_id already exists with different data")
    row_count = db.execute(
        select(func.count()).select_from(TrialResponse).where(
            TrialResponse.submission_id == submission.id
        )
    ).scalar_one()
    response = {
        "ok": True,
        "submission_id": submission.id,
        "rows": row_count,
        "duplicate": True,
    }
    if submission.study_id == QUALIFICATION_STUDY_ID:
        result = qualification_result(submission.raw_payload or {})
        if result:
            response.update(result)
    return JSONResponse(response)


@app.post("/api/submissions")
async def create_submission(payload: SubmissionPayload, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    validate_submission(payload)
    submission_id = normalized_submission_id(payload.submission_id)
    payload.submission_id = submission_id
    client_payload = payload_dict(payload)
    digest = payload_sha256(client_payload)

    existing = db.get(Submission, submission_id)
    if existing:
        return duplicate_response(db, existing, digest)

    participant = payload.participant or {}
    post_survey = payload.post_survey or {}
    prolific_pid = str(participant.get("PROLIFIC_PID") or "")
    prolific_study_id = str(participant.get("STUDY_ID") or "")
    prolific_session_id = str(participant.get("SESSION_ID") or "")
    participant_id = str(
        prolific_pid
        or post_survey.get("participant_id")
        or participant.get("participant")
        or ""
    )

    qualification = qualification_result(client_payload)
    raw_payload = dict(client_payload)
    raw_payload["server"] = {
        "submission_id": submission_id,
        "client_host": request.client.host if request.client else "",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    if qualification:
        raw_payload["server"].update(qualification)

    db.add(
        Submission(
            id=submission_id,
            study_id=payload.study_id,
            task_type=payload.task_type or "",
            target_accent=payload.target_accent or "",
            form_id=payload.form_id or "",
            form_assignment_basis=payload.form_assignment_basis or "",
            prolific_pid=prolific_pid,
            prolific_study_id=prolific_study_id,
            prolific_session_id=prolific_session_id,
            participant_id=participant_id,
            page_url=payload.page_url or "",
            user_agent=payload.user_agent or request.headers.get("user-agent", ""),
            started_at_ms=payload.started_at,
            submitted_at_ms=payload.submitted_at,
            payload_sha256=digest,
            raw_payload=raw_payload,
        )
    )

    for row in payload.rows:
        qid = str(row.get("qid") or "")
        expected_accent = str(row.get("expected_accent") or "")
        primary_correct = as_int(row.get("primary_accent_correct"))
        if payload.study_id == QUALIFICATION_STUDY_ID:
            expected_accent = QUALIFICATION_ANSWER_KEY.get(qid, "")
            choice = str(row.get("accent_choice") or row.get("primary_accent") or "")
            primary_correct = int(choice == expected_accent)
        db.add(
            TrialResponse(
                submission_id=submission_id,
                study_id=payload.study_id,
                task_type=payload.task_type or str(row.get("task_type") or ""),
                qid=qid,
                display_index=as_int(row.get("display_index")),
                page=as_int(row.get("page")),
                condition=str(row.get("condition") or ""),
                condition_label=str(row.get("condition_label") or ""),
                expected_accent=expected_accent,
                audio=str(row.get("audio") or ""),
                source_index=as_int(row.get("source_index")),
                accent_choice=str(row.get("accent_choice") or ""),
                confidence=as_int(row.get("confidence")),
                naturalness_choice=str(row.get("naturalness_choice") or ""),
                naturalness_correct=as_int(row.get("naturalness_correct")),
                primary_accent=str(row.get("primary_accent") or ""),
                primary_accent_correct=primary_correct,
                secondary_accent=str(row.get("secondary_accent") or ""),
                secondary_influence=as_int(row.get("secondary_influence")),
                playback_count=as_int(row.get("playback_count")),
                similarity_rating=as_int(row.get("similarity_rating")),
                mos_rating=as_int(row.get("mos_rating")),
                mos_label=str(row.get("mos_label") or ""),
                distortion_label=str(row.get("distortion_label") or ""),
                response_ts_ms=as_float(row.get("response_ts")),
            )
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(Submission, submission_id)
        if existing:
            return duplicate_response(db, existing, digest)
        raise

    response = {
        "ok": True,
        "submission_id": submission_id,
        "rows": len(payload.rows),
        "duplicate": False,
    }
    if qualification:
        response.update(qualification)
    return JSONResponse(response)


@app.get("/api/submissions/{submission_id}/status")
def submission_status(submission_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    row_count = db.execute(
        select(func.count()).select_from(TrialResponse).where(
            TrialResponse.submission_id == submission_id
        )
    ).scalar_one()
    return {
        "ok": True,
        "stored": True,
        "submission_id": submission_id,
        "rows": row_count,
    }


@app.get("/api/submissions")
def list_submissions(_: None = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    records = db.execute(select(Submission).order_by(Submission.received_at.desc())).scalars().all()
    return [
        {
            "id": r.id,
            "study_id": r.study_id,
            "task_type": r.task_type,
            "target_accent": r.target_accent,
            "form_id": r.form_id,
            "form_assignment_basis": r.form_assignment_basis,
            "prolific_pid": r.prolific_pid,
            "prolific_study_id": r.prolific_study_id,
            "prolific_session_id": r.prolific_session_id,
            "participant_id": r.participant_id,
            "received_at": r.received_at.isoformat() if r.received_at else "",
        }
        for r in records
    ]


def csv_response(filename: str, rows: list[dict[str, Any]], fieldnames: list[str]) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/submissions.csv")
def export_submissions(_: None = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    records = db.execute(select(Submission).order_by(Submission.received_at.asc())).scalars().all()
    rows = [
        {
            "submission_id": r.id,
            "study_id": r.study_id,
            "task_type": r.task_type,
            "target_accent": r.target_accent,
            "form_id": r.form_id,
            "form_assignment_basis": r.form_assignment_basis,
            "prolific_pid": r.prolific_pid,
            "prolific_study_id": r.prolific_study_id,
            "prolific_session_id": r.prolific_session_id,
            "participant_id": r.participant_id,
            "received_at": r.received_at.isoformat() if r.received_at else "",
            "started_at_ms": r.started_at_ms,
            "submitted_at_ms": r.submitted_at_ms,
            "page_url": r.page_url,
            "user_agent": r.user_agent,
        }
        for r in records
    ]
    return csv_response("submissions.csv", rows, list(rows[0].keys()) if rows else ["submission_id"])


@app.get("/api/export/trial_responses.csv")
def export_trial_responses(_: None = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    records = db.execute(select(TrialResponse).order_by(TrialResponse.submission_id.asc(), TrialResponse.display_index.asc())).scalars().all()
    rows = [
        {
            "submission_id": r.submission_id,
            "study_id": r.study_id,
            "task_type": r.task_type,
            "qid": r.qid,
            "display_index": r.display_index,
            "page": r.page,
            "condition": r.condition,
            "condition_label": r.condition_label,
            "expected_accent": r.expected_accent,
            "audio": r.audio,
            "source_index": r.source_index,
            "accent_choice": r.accent_choice,
            "confidence": r.confidence,
            "naturalness_choice": r.naturalness_choice,
            "naturalness_correct": r.naturalness_correct,
            "primary_accent": r.primary_accent,
            "primary_accent_correct": r.primary_accent_correct,
            "secondary_accent": r.secondary_accent,
            "secondary_influence": r.secondary_influence,
            "playback_count": r.playback_count,
            "similarity_rating": r.similarity_rating,
            "mos_rating": r.mos_rating,
            "mos_label": r.mos_label,
            "distortion_label": r.distortion_label,
            "response_ts_ms": r.response_ts_ms,
        }
        for r in records
    ]
    return csv_response("trial_responses.csv", rows, list(rows[0].keys()) if rows else ["submission_id"])


@app.get("/api/export/raw.jsonl")
def export_raw_jsonl(_: None = Depends(require_admin), db: Session = Depends(get_db)) -> PlainTextResponse:
    records = db.execute(select(Submission).order_by(Submission.received_at.asc())).scalars().all()
    lines = [json.dumps(r.raw_payload, ensure_ascii=False) for r in records]
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8787")), reload=True)
