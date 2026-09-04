"""SQLite-backed audit trail for reconciliation decisions.

Every matching decision — from every tier — is logged here with enough
detail for a human to reconstruct any decision after the fact.
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from recon.config import settings


SCHEMA_SQL = """
-- Every matching decision, one row per source-record pair
CREATE TABLE IF NOT EXISTS match_decisions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id            TEXT NOT NULL,
    record_source       TEXT NOT NULL,
    record_id           TEXT NOT NULL,
    matched_source      TEXT,
    matched_record_id   TEXT,
    match_tier          INTEGER,
    confidence          REAL,
    match_rules_applied TEXT,
    decision            TEXT NOT NULL,
    explanation         TEXT DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- AI investigation details (Tier 3 only)
CREATE TABLE IF NOT EXISTS ai_investigations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    match_decision_id   INTEGER NOT NULL REFERENCES match_decisions(id),
    llm_model           TEXT NOT NULL,
    prompt_text         TEXT NOT NULL,
    response_text       TEXT NOT NULL,
    diagnosis_category  TEXT,
    suggested_action    TEXT,
    explanation         TEXT,
    token_count_input   INTEGER,
    token_count_output  INTEGER,
    latency_ms          INTEGER,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Batch-level summary
CREATE TABLE IF NOT EXISTS batch_runs (
    id                  TEXT PRIMARY KEY,
    started_at          TEXT NOT NULL,
    completed_at        TEXT,
    total_records       INTEGER,
    tier1_matched       INTEGER DEFAULT 0,
    tier2_matched       INTEGER DEFAULT 0,
    tier3_matched       INTEGER DEFAULT 0,
    human_review        INTEGER DEFAULT 0,
    unreconcilable      INTEGER DEFAULT 0,
    false_matches       INTEGER DEFAULT 0,
    processing_time_ms  INTEGER,
    config_snapshot     TEXT
);

CREATE INDEX IF NOT EXISTS idx_match_decisions_batch ON match_decisions(batch_id);
CREATE INDEX IF NOT EXISTS idx_match_decisions_record ON match_decisions(record_source, record_id);
CREATE INDEX IF NOT EXISTS idx_ai_investigations_decision ON ai_investigations(match_decision_id);
"""


class AuditDB:
    """SQLite audit trail database.

    Usage:
        db = AuditDB()
        db.initialize()
        batch_id = db.start_batch(config_snapshot={...})
        decision_id = db.log_match(batch_id, ...)
        db.complete_batch(batch_id, stats={...})
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.audit_db_path

    def initialize(self) -> None:
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def start_batch(self, config_snapshot: dict) -> str:
        """Start a new reconciliation batch run. Returns batch_id."""
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO batch_runs (id, started_at, config_snapshot)
                   VALUES (?, ?, ?)""",
                (batch_id, now, json.dumps(config_snapshot)),
            )
        return batch_id

    def log_match(
        self,
        batch_id: str,
        record_source: str,
        record_id: str,
        matched_source: Optional[str],
        matched_record_id: Optional[str],
        match_tier: Optional[int],
        confidence: Optional[float],
        rules_applied: list[str],
        decision: str,
        explanation: str = "",
    ) -> int:
        """Log a single matching decision. Returns the decision row ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO match_decisions
                   (batch_id, record_source, record_id, matched_source,
                    matched_record_id, match_tier, confidence,
                    match_rules_applied, decision, explanation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    batch_id,
                    record_source,
                    record_id,
                    matched_source,
                    matched_record_id,
                    match_tier,
                    confidence,
                    json.dumps(rules_applied),
                    decision,
                    explanation,
                ),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def update_decision_to_match(
        self,
        decision_id: int,
        matched_source: str,
        matched_record_id: str,
        confidence: float,
        explanation: str
    ) -> None:
        """Update an existing decision (usually unreconcilable) to a matched state (used by Tier 3 AI)."""
        with self._connect() as conn:
            conn.execute(
                """UPDATE match_decisions 
                   SET decision = 'matched',
                       matched_source = ?,
                       matched_record_id = ?,
                       confidence = ?,
                       explanation = ?
                   WHERE id = ?""",
                (matched_source, matched_record_id, confidence, explanation, decision_id)
            )

    def log_ai_investigation(
        self,
        match_decision_id: int,
        llm_model: str,
        prompt_text: str,
        response_text: str,
        diagnosis_category: Optional[str] = None,
        suggested_action: Optional[str] = None,
        explanation: Optional[str] = None,
        token_count_input: Optional[int] = None,
        token_count_output: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ) -> int:
        """Log an AI investigation (Tier 3 only). Returns the investigation row ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO ai_investigations
                   (match_decision_id, llm_model, prompt_text, response_text,
                    diagnosis_category, suggested_action, explanation,
                    token_count_input, token_count_output, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    match_decision_id,
                    llm_model,
                    prompt_text,
                    response_text,
                    diagnosis_category,
                    suggested_action,
                    explanation,
                    token_count_input,
                    token_count_output,
                    latency_ms,
                ),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def complete_batch(
        self,
        batch_id: str,
        total_records: int,
        tier1_matched: int,
        tier2_matched: int,
        tier3_matched: int,
        human_review: int,
        unreconcilable: int,
        processing_time_ms: int,
        false_matches: int = 0,
    ) -> None:
        """Mark a batch as complete with summary statistics."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """UPDATE batch_runs SET
                   completed_at = ?, total_records = ?,
                   tier1_matched = ?, tier2_matched = ?, tier3_matched = ?,
                   human_review = ?, unreconcilable = ?,
                   false_matches = ?, processing_time_ms = ?
                   WHERE id = ?""",
                (
                    now,
                    total_records,
                    tier1_matched,
                    tier2_matched,
                    tier3_matched,
                    human_review,
                    unreconcilable,
                    false_matches,
                    processing_time_ms,
                    batch_id,
                ),
            )

    def get_batch_summary(self, batch_id: str) -> Optional[dict]:
        """Retrieve batch summary as a dict."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM batch_runs WHERE id = ?", (batch_id,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)

    def get_decisions_for_batch(self, batch_id: str) -> list[dict]:
        """Retrieve all decisions for a batch."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM match_decisions WHERE batch_id = ? ORDER BY id",
                (batch_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_ai_investigation(self, decision_id: int) -> Optional[dict]:
        """Retrieve AI investigation details for a decision."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ai_investigations WHERE match_decision_id = ?",
                (decision_id,),
            ).fetchone()
            if row is None:
                return None
            return dict(row)
