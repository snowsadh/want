from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.api.app.contracts import SavedLook, SavedLookCreate, UserProfile

MIGRATION_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class Database:
    def __init__(self, path: Path, migrations_dir: Path) -> None:
        self.path = path
        self.migrations_dir = migrations_dir

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row["version"]
                for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
            }
        for migration in sorted(self.migrations_dir.glob("*.up.sql")):
            version = migration.name.removesuffix(".up.sql")
            if version in applied:
                continue
            if not MIGRATION_NAME_RE.fullmatch(version):
                raise RuntimeError(f"Unsafe migration name: {version}")
            escaped_version = version.replace("'", "''")
            applied_at = now_iso().replace("'", "''")
            script = (
                "BEGIN IMMEDIATE;\n"
                + migration.read_text()
                + f"\nINSERT INTO schema_migrations(version, applied_at) "
                f"VALUES ('{escaped_version}', '{applied_at}');\nCOMMIT;"
            )
            with self.connect() as connection:
                connection.executescript(script)

    def get_profile(self) -> UserProfile | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT photo_ref, created_at, updated_at "
                "FROM profiles WHERE singleton_id = 1"
            ).fetchone()
        return UserProfile.model_validate(dict(row)) if row else None

    def set_profile_photo(self, photo_ref: str) -> UserProfile:
        timestamp = now_iso()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM profiles WHERE singleton_id = 1"
            ).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            connection.execute(
                "INSERT INTO profiles(singleton_id, photo_ref, created_at, updated_at) "
                "VALUES (1, ?, ?, ?) "
                "ON CONFLICT(singleton_id) DO UPDATE SET "
                "photo_ref = excluded.photo_ref, updated_at = excluded.updated_at",
                (photo_ref, created_at, timestamp),
            )
        profile = self.get_profile()
        if profile is None:
            raise RuntimeError("Profile photo did not persist")
        return profile

    def create_saved_look(self, value: SavedLookCreate) -> SavedLook:
        saved_id = str(uuid4())
        timestamp = now_iso()
        snapshot_json = value.snapshot.model_dump_json()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO saved_looks("
                "id, source_url, capture_ref, personalized_result_ref, "
                "snapshot_json, created_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    saved_id,
                    str(value.source_url) if value.source_url else None,
                    value.capture_ref,
                    value.personalized_result_ref,
                    snapshot_json,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_saved_look(saved_id)

    def list_saved_looks(self) -> list[SavedLook]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, source_url, capture_ref, personalized_result_ref, "
                "snapshot_json, created_at, updated_at FROM saved_looks "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [self._saved_from_row(row) for row in rows]

    def get_saved_look(self, saved_id: str) -> SavedLook:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, source_url, capture_ref, personalized_result_ref, "
                "snapshot_json, created_at, updated_at FROM saved_looks WHERE id = ?",
                (saved_id,),
            ).fetchone()
        if row is None:
            raise LookupError(saved_id)
        return self._saved_from_row(row)

    def delete_saved_look(self, saved_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM saved_looks WHERE id = ?", (saved_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _saved_from_row(row: sqlite3.Row) -> SavedLook:
        values: dict[str, Any] = dict(row)
        values["snapshot"] = json.loads(values.pop("snapshot_json"))
        return SavedLook.model_validate(values)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
