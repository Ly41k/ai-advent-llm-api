"""Persistent periodic GitHub collection and deterministic aggregation (UTC)."""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from github_api import GitHubApi


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


class Scheduler:
    def __init__(self, db_path=None, api=None, clock=utc_now):
        self.db_path = Path(db_path or os.getenv("BUBLIK_DB_PATH", Path(__file__).with_name("schedule.db")))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.api = api or GitHubApi()
        self.clock = clock
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY, owner TEXT NOT NULL, repo TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL, next_run TEXT NOT NULL,
                    last_error TEXT, UNIQUE(owner, repo)
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id),
                    captured_at TEXT NOT NULL, stars INTEGER NOT NULL,
                    forks INTEGER NOT NULL, open_issues INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id),
                    executed_at TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL
                );
            """)

    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def schedule(self, owner, repo, interval_minutes):
        owner = GitHubApi._validate_name("owner", owner)
        repo = GitHubApi._validate_name("repo", repo)
        if type(interval_minutes) is not int or not 1 <= interval_minutes <= 10080:
            raise ValueError("interval_minutes must be an integer between 1 and 10080")
        now = iso(self.clock())
        with self._db() as db:
            db.execute("""INSERT INTO jobs(owner, repo, interval_minutes, next_run)
                VALUES(?, ?, ?, ?) ON CONFLICT(owner, repo) DO UPDATE SET
                interval_minutes=excluded.interval_minutes, next_run=excluded.next_run,
                last_error=NULL""", (owner, repo, interval_minutes, now))
        return {"owner": owner, "repo": repo, "interval_minutes": interval_minutes,
                "next_run": now}

    def jobs(self):
        with self._db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY id")]

    def summary(self, owner, repo, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        with self._db() as db:
            job = db.execute("SELECT * FROM jobs WHERE owner=? AND repo=?", (owner, repo)).fetchone()
            if job is None:
                raise ValueError("Scheduled repository not found")
            rows = list(db.execute("""SELECT captured_at, stars, forks, open_issues
                FROM snapshots WHERE job_id=? ORDER BY id DESC LIMIT ?""", (job["id"], limit)))
        if not rows:
            return {"repository": f"{owner}/{repo}", "samples": 0,
                    "next_run": job["next_run"], "last_error": job["last_error"]}
        newest, oldest = rows[0], rows[-1]
        return {"repository": f"{owner}/{repo}", "samples": len(rows),
                "from": oldest["captured_at"], "to": newest["captured_at"],
                "latest": {key: newest[key] for key in ("stars", "forks", "open_issues")},
                "change": {key: newest[key] - oldest[key]
                           for key in ("stars", "forks", "open_issues")},
                "next_run": job["next_run"], "last_error": job["last_error"]}

    def run_due(self):
        """Run all currently due jobs; record errors and advance the schedule."""
        now = self.clock()
        with self._db() as db:
            due = [dict(row) for row in db.execute(
                "SELECT * FROM jobs WHERE next_run <= ? ORDER BY next_run, id", (iso(now),))]
        results = []
        for job in due:
            try:
                data = self.api.get_repository(job["owner"], job["repo"])
                status, detail = "ok", "snapshot saved"
            except Exception as error:
                status, detail = "error", f"{type(error).__name__}: {error}"
            # Advance from now; a restart never replays an unbounded backlog.
            next_run = iso(now + timedelta(minutes=job["interval_minutes"]))
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute("SELECT next_run FROM jobs WHERE id=?", (job["id"],)).fetchone()
                if current is None or current["next_run"] != job["next_run"]:
                    continue
                if status == "ok":
                    db.execute("""INSERT INTO snapshots(job_id, captured_at, stars, forks, open_issues)
                        VALUES(?, ?, ?, ?, ?)""", (job["id"], iso(now), data["stars"],
                                               data["forks"], data["open_issues"]))
                db.execute("INSERT INTO runs(job_id, executed_at, status, detail) VALUES(?, ?, ?, ?)",
                           (job["id"], iso(now), status, detail))
                db.execute("UPDATE jobs SET next_run=?, last_error=? WHERE id=?",
                           (next_run, detail if status == "error" else None, job["id"]))
            results.append({"repository": f"{job['owner']}/{job['repo']}", "status": status,
                            "detail": detail, "summary": self.summary(job["owner"], job["repo"])})
        return results
