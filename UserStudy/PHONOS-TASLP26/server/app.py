from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./responses.db")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",") if x.strip()]
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String, primary_key=True)
    study_id = Column(String, index=True, nullable=False)
    task_type = Column(String, index=True, default="")
    target_accent = Column(String, index=True, default="")
    prolific_pid = Column(String, index=True, default="")
    prolific_study_id = Column(String, index=True, default="")
    prolific_session_id = Column(String, index=True, default="")
    participant_id = Column(String, index=True, default="")
    page_url = Column(Text, default="")
    user_agent = Column(Text, default="")
    started_at_ms = Column(Float, nullable=True)
    submitted_at_ms = Column(Float, nullable=True)
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
    similarity_rating = Column(Integer, nullable=True)
    mos_rating = Column(Integer, nullable=True)
    mos_label = Column(String, index=True, default="")
    distortion_label = Column(Text, default="")
    response_ts_ms = Column(Float, nullable=True)


class SubmissionPayload(BaseModel):
    study_id: str = Field(..., min_length=1)
    task_type: str | None = ""
    title: str | None = ""
    target_accent: str | None = ""
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


def init_db() -> None:
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(submissions)")}
            if "prolific_study_id" not in cols:
                conn.exec_driver_sql("ALTER TABLE submissions ADD COLUMN prolific_study_id VARCHAR DEFAULT ''")
            if "prolific_session_id" not in cols:
                conn.exec_driver_sql("ALTER TABLE submissions ADD COLUMN prolific_session_id VARCHAR DEFAULT ''")
            trial_cols = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(trial_responses)")
            }
            if "similarity_rating" not in trial_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE trial_responses ADD COLUMN similarity_rating INTEGER"
                )


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(token: str | None = Query(default=None), x_admin_token: str | None = Header(default=None)) -> None:
    if not ADMIN_TOKEN:
        return
    supplied = token or x_admin_token or ""
    if supplied != ADMIN_TOKEN:
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
def health() -> dict[str, str]:
    return {"ok": "true", "database": DATABASE_URL.split(":", 1)[0]}


@app.post("/api/submissions")
async def create_submission(payload: SubmissionPayload, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    submission_id = uuid4().hex
    participant = payload.participant or {}
    post_survey = payload.post_survey or {}
    prolific_pid = str(participant.get("PROLIFIC_PID") or "")
    prolific_study_id = str(participant.get("STUDY_ID") or "")
    prolific_session_id = str(participant.get("SESSION_ID") or "")
    participant_id = str(prolific_pid or post_survey.get("participant_id") or participant.get("participant") or "")

    raw_payload = payload.dict()
    raw_payload["server"] = {
        "submission_id": submission_id,
        "client_host": request.client.host if request.client else "",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    db.add(
        Submission(
            id=submission_id,
            study_id=payload.study_id,
            task_type=payload.task_type or "",
            target_accent=payload.target_accent or "",
            prolific_pid=prolific_pid,
            prolific_study_id=prolific_study_id,
            prolific_session_id=prolific_session_id,
            participant_id=participant_id,
            page_url=payload.page_url or "",
            user_agent=payload.user_agent or request.headers.get("user-agent", ""),
            started_at_ms=payload.started_at,
            submitted_at_ms=payload.submitted_at,
            raw_payload=raw_payload,
        )
    )

    for row in payload.rows:
        db.add(
            TrialResponse(
                submission_id=submission_id,
                study_id=payload.study_id,
                task_type=payload.task_type or str(row.get("task_type") or ""),
                qid=str(row.get("qid") or ""),
                display_index=as_int(row.get("display_index")),
                page=as_int(row.get("page")),
                condition=str(row.get("condition") or ""),
                condition_label=str(row.get("condition_label") or ""),
                expected_accent=str(row.get("expected_accent") or ""),
                audio=str(row.get("audio") or ""),
                source_index=as_int(row.get("source_index")),
                accent_choice=str(row.get("accent_choice") or ""),
                confidence=as_int(row.get("confidence")),
                similarity_rating=as_int(row.get("similarity_rating")),
                mos_rating=as_int(row.get("mos_rating")),
                mos_label=str(row.get("mos_label") or ""),
                distortion_label=str(row.get("distortion_label") or ""),
                response_ts_ms=as_float(row.get("response_ts")),
            )
        )

    db.commit()
    return JSONResponse({"ok": True, "submission_id": submission_id, "rows": len(payload.rows)})


@app.get("/api/submissions")
def list_submissions(_: None = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    records = db.execute(select(Submission).order_by(Submission.received_at.desc())).scalars().all()
    return [
        {
            "id": r.id,
            "study_id": r.study_id,
            "task_type": r.task_type,
            "target_accent": r.target_accent,
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
