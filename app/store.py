"""승인 워크플로(F8) + 감사로그(F9) — SQLite 저장소."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("JB_DB_PATH",
                              Path(__file__).resolve().parent / "data" / "app.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  title TEXT NOT NULL,
  submitter TEXT NOT NULL,
  content_type TEXT NOT NULL,
  language TEXT NOT NULL,
  product_facts TEXT,
  text TEXT NOT NULL,
  report_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
  decided_by TEXT,
  decided_at TEXT,
  decision_comment TEXT
);
CREATE TABLE IF NOT EXISTS translations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  submission_id INTEGER NOT NULL REFERENCES submissions(id),
  created_at TEXT NOT NULL,
  target_lang TEXT NOT NULL,
  text TEXT NOT NULL,
  engine TEXT,
  report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  submission_id INTEGER,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  detail TEXT
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def log(conn: sqlite3.Connection, submission_id: int | None, actor: str, action: str, detail: str = ""):
    conn.execute("INSERT INTO audit_log (ts, submission_id, actor, action, detail) VALUES (?,?,?,?,?)",
                 (_now(), submission_id, actor, action, detail))


def create_submission(title: str, submitter: str, content_type: str, language: str,
                      product_facts: str, text: str, report: dict,
                      autopilot_summary: str = "") -> dict:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO submissions (created_at, title, submitter, content_type, language, product_facts, text, report_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (_now(), title, submitter, content_type, language, product_facts, text,
             json.dumps(report, ensure_ascii=False)))
        sid = cur.lastrowid
        # 책임소재: AI 자동개선과 사람의 제출/승인을 분리 기록 (내부통제·검사 대응, 설계 §8)
        if autopilot_summary:
            log(conn, sid, "AI-오토파일럿", "auto_remediate", autopilot_summary)
        log(conn, sid, submitter, "submit",
            f"AI 1차심의 {report.get('grade_emoji','')}{report.get('grade_label','')}({report.get('score','')}점) — 검토 요청")
    return get_submission(sid)


def list_submissions() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM submissions ORDER BY id DESC").fetchall()
    return [_row_to_submission(r, include_report=False) for r in rows]


def get_submission(sid: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        tr = conn.execute("SELECT * FROM translations WHERE submission_id=? ORDER BY id DESC", (sid,)).fetchall()
    sub = _row_to_submission(row, include_report=True)
    sub["translations"] = [
        {"id": t["id"], "created_at": t["created_at"], "target_lang": t["target_lang"],
         "text": t["text"], "engine": t["engine"], "report": json.loads(t["report_json"])}
        for t in tr
    ]
    return sub


def decide(sid: int, action: str, actor: str, comment: str = "") -> dict | None:
    status = {"approve": "approved", "reject": "rejected"}[action]
    with _conn() as conn:
        row = conn.execute("SELECT id FROM submissions WHERE id=?", (sid,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE submissions SET status=?, decided_by=?, decided_at=?, decision_comment=? WHERE id=?",
            (status, actor, _now(), comment, sid))
        label = "승인 — 배포가능 상태 전환" if status == "approved" else "반려 — 수정 후 재제출 필요"
        log(conn, sid, actor, action, f"{label}" + (f" / 코멘트: {comment}" if comment else ""))
    return get_submission(sid)


def add_comment(sid: int, actor: str, comment: str) -> None:
    with _conn() as conn:
        log(conn, sid, actor, "comment", comment)


def save_translation(sid: int, target_lang: str, text: str, engine: str, report: dict, actor: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO translations (submission_id, created_at, target_lang, text, engine, report_json) "
            "VALUES (?,?,?,?,?,?)",
            (sid, _now(), target_lang, text, engine, json.dumps(report, ensure_ascii=False)))
        log(conn, sid, actor, "translate",
            f"{target_lang} 버전 생성({engine}) + 재심의 {report.get('grade_emoji','')}{report.get('grade_label','')}({report.get('score','')}점)")


def audit_trail(submission_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if submission_id:
            rows = conn.execute("SELECT * FROM audit_log WHERE submission_id=? ORDER BY id DESC",
                                (submission_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]


def _row_to_submission(row: sqlite3.Row, include_report: bool) -> dict:
    d = dict(row)
    report = json.loads(d.pop("report_json"))
    if include_report:
        d["report"] = report
    else:
        d["report_summary"] = {k: report.get(k) for k in
                               ("score", "grade", "grade_label", "grade_emoji", "counts")}
    return d
