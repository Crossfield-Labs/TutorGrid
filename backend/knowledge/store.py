from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from backend.knowledge.models import KnowledgeChunkDraft


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteKnowledgeStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_courses (
                    course_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_files (
                    file_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    file_ext TEXT NOT NULL,
                    parse_status TEXT NOT NULL,
                    parse_error TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_jobs (
                    job_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    source_page INTEGER NOT NULL,
                    source_section TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_files_course
                ON knowledge_files(course_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_course
                ON knowledge_jobs(course_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_course
                ON knowledge_chunks(course_id, chunk_index ASC);
                """
            )
            self._ensure_chunk_embedding_column(connection)
            connection.commit()

    @staticmethod
    def _ensure_chunk_embedding_column(connection: sqlite3.Connection) -> None:
        rows = connection.execute("PRAGMA table_info(knowledge_chunks)").fetchall()
        columns = {str(row["name"]).lower() for row in rows}
        if "embedding_json" in columns:
            return
        connection.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding_json TEXT NOT NULL DEFAULT '[]'")

    def create_course(self, *, name: str, description: str) -> dict[str, Any]:
        now = _utcnow()
        course_id = uuid4().hex
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_courses (
                    course_id, name, description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (course_id, name, description, now, now),
            )
            connection.commit()
        return {
            "courseId": course_id,
            "name": name,
            "description": description,
            "createdAt": now,
            "updatedAt": now,
        }

    def get_course(self, course_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT course_id, name, description, created_at, updated_at
                FROM knowledge_courses
                WHERE course_id = ?
                """,
                (course_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "courseId": str(row["course_id"]),
            "name": str(row["name"]),
            "description": str(row["description"]),
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }

    def list_courses(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT course_id, name, description, created_at, updated_at
                FROM knowledge_courses
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        return [
            {
                "courseId": str(row["course_id"]),
                "name": str(row["name"]),
                "description": str(row["description"]),
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in rows
        ]

    def delete_course(self, *, course_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            course_row = connection.execute(
                "SELECT course_id FROM knowledge_courses WHERE course_id = ?",
                (course_id,),
            ).fetchone()
            if course_row is None:
                return {
                    "deleted": False,
                    "courseId": course_id,
                    "fileCount": 0,
                    "chunkCount": 0,
                    "jobCount": 0,
                    "storedPaths": [],
                    "fileIds": [],
                }
            file_rows = connection.execute(
                """
                SELECT file_id, stored_path
                FROM knowledge_files
                WHERE course_id = ?
                """,
                (course_id,),
            ).fetchall()
            chunk_row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM knowledge_chunks WHERE course_id = ?",
                (course_id,),
            ).fetchone()
            job_row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM knowledge_jobs WHERE course_id = ?",
                (course_id,),
            ).fetchone()
            connection.execute("DELETE FROM knowledge_chunks WHERE course_id = ?", (course_id,))
            connection.execute("DELETE FROM knowledge_jobs WHERE course_id = ?", (course_id,))
            connection.execute("DELETE FROM knowledge_files WHERE course_id = ?", (course_id,))
            connection.execute("DELETE FROM knowledge_courses WHERE course_id = ?", (course_id,))
            connection.commit()
        file_ids = [str(row["file_id"]) for row in file_rows]
        stored_paths = [str(row["stored_path"]) for row in file_rows]
        return {
            "deleted": True,
            "courseId": course_id,
            "fileCount": len(file_rows),
            "chunkCount": int(chunk_row["cnt"] if chunk_row is not None else 0),
            "jobCount": int(job_row["cnt"] if job_row is not None else 0),
            "storedPaths": stored_paths,
            "fileIds": file_ids,
        }

    def create_file_record(
        self,
        *,
        course_id: str,
        original_name: str,
        stored_path: str,
        file_ext: str,
        source_type: str,
    ) -> dict[str, Any]:
        now = _utcnow()
        file_id = uuid4().hex
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_files (
                    file_id, course_id, original_name, stored_path, file_ext,
                    parse_status, parse_error, source_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, course_id, original_name, stored_path, file_ext, "processing", "", source_type, now, now),
            )
            connection.commit()
        return {
            "fileId": file_id,
            "courseId": course_id,
            "originalName": original_name,
            "storedPath": stored_path,
            "fileExt": file_ext,
            "parseStatus": "processing",
            "parseError": "",
            "sourceType": source_type,
            "createdAt": now,
            "updatedAt": now,
        }

    def get_file(self, *, file_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    file_id, course_id, original_name, stored_path, file_ext,
                    parse_status, parse_error, source_type, created_at, updated_at
                FROM knowledge_files
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "fileId": str(row["file_id"]),
            "courseId": str(row["course_id"]),
            "originalName": str(row["original_name"]),
            "storedPath": str(row["stored_path"]),
            "fileExt": str(row["file_ext"]),
            "parseStatus": str(row["parse_status"]),
            "parseError": str(row["parse_error"]),
            "sourceType": str(row["source_type"]),
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }

    def update_file_status(self, *, file_id: str, status: str, parse_error: str = "") -> None:
        now = _utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE knowledge_files
                SET parse_status = ?, parse_error = ?, updated_at = ?
                WHERE file_id = ?
                """,
                (status, parse_error, now, file_id),
            )
            connection.commit()

    def list_files(self, *, course_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    file_id, course_id, original_name, stored_path, file_ext,
                    parse_status, parse_error, source_type, created_at, updated_at
                FROM knowledge_files
                WHERE course_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (course_id, max(1, limit)),
            ).fetchall()
        return [
            {
                "fileId": str(row["file_id"]),
                "courseId": str(row["course_id"]),
                "originalName": str(row["original_name"]),
                "storedPath": str(row["stored_path"]),
                "fileExt": str(row["file_ext"]),
                "parseStatus": str(row["parse_status"]),
                "parseError": str(row["parse_error"]),
                "sourceType": str(row["source_type"]),
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in rows
        ]

    def delete_file(self, *, file_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            file_row = connection.execute(
                """
                SELECT file_id, course_id, stored_path
                FROM knowledge_files
                WHERE file_id = ?
                """,
                (file_id,),
            ).fetchone()
            if file_row is None:
                return {
                    "deleted": False,
                    "fileId": file_id,
                    "courseId": "",
                    "storedPath": "",
                    "chunkCount": 0,
                    "jobCount": 0,
                }
            chunk_row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM knowledge_chunks WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            job_row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM knowledge_jobs WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            connection.execute("DELETE FROM knowledge_chunks WHERE file_id = ?", (file_id,))
            connection.execute("DELETE FROM knowledge_jobs WHERE file_id = ?", (file_id,))
            connection.execute("DELETE FROM knowledge_files WHERE file_id = ?", (file_id,))
            connection.commit()
        return {
            "deleted": True,
            "fileId": str(file_row["file_id"]),
            "courseId": str(file_row["course_id"]),
            "storedPath": str(file_row["stored_path"]),
            "chunkCount": int(chunk_row["cnt"] if chunk_row is not None else 0),
            "jobCount": int(job_row["cnt"] if job_row is not None else 0),
        }

    def create_job(self, *, course_id: str, file_id: str, status: str, progress: float, message: str) -> dict[str, Any]:
        now = _utcnow()
        job_id = uuid4().hex
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_jobs (
                    job_id, course_id, file_id, status, progress, message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, course_id, file_id, status, float(progress), message, now, now),
            )
            connection.commit()
        return {
            "jobId": job_id,
            "courseId": course_id,
            "fileId": file_id,
            "status": status,
            "progress": float(progress),
            "message": message,
            "createdAt": now,
            "updatedAt": now,
        }

    def update_job(self, *, job_id: str, status: str, progress: float, message: str) -> None:
        now = _utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE knowledge_jobs
                SET status = ?, progress = ?, message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, float(progress), message, now, job_id),
            )
            connection.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT job_id, course_id, file_id, status, progress, message, created_at, updated_at
                FROM knowledge_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "jobId": str(row["job_id"]),
            "courseId": str(row["course_id"]),
            "fileId": str(row["file_id"]),
            "status": str(row["status"]),
            "progress": float(row["progress"]),
            "message": str(row["message"]),
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }

    def list_jobs(self, *, course_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT job_id, course_id, file_id, status, progress, message, created_at, updated_at
                FROM knowledge_jobs
                WHERE course_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (course_id, max(1, int(limit))),
            ).fetchall()
        return [
            {
                "jobId": str(row["job_id"]),
                "courseId": str(row["course_id"]),
                "fileId": str(row["file_id"]),
                "status": str(row["status"]),
                "progress": float(row["progress"]),
                "message": str(row["message"]),
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in rows
        ]

    def replace_file_chunks(self, *, course_id: str, file_id: str, chunks: list[KnowledgeChunkDraft]) -> int:
        now = _utcnow()
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM knowledge_chunks WHERE file_id = ?", (file_id,))
            for chunk in chunks:
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id, course_id, file_id, chunk_index, source_page, source_section,
                        content, token_estimate, embedding_json, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        course_id,
                        file_id,
                        int(chunk.chunk_index),
                        int(chunk.source_page),
                        chunk.source_section,
                        chunk.content,
                        int(chunk.token_estimate),
                        json.dumps(chunk.embedding, ensure_ascii=False),
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
            connection.commit()
        return len(chunks)

    def list_chunks(self, *, course_id: str, limit: int = 100, query: str = "") -> list[dict[str, Any]]:
        query_text = query.strip()
        with closing(self._connect()) as connection:
            if query_text:
                rows = connection.execute(
                    """
                    SELECT
                        chunk_id, course_id, file_id, chunk_index, source_page, source_section,
                        content, token_estimate, embedding_json, metadata_json, created_at, updated_at
                    FROM knowledge_chunks
                    WHERE course_id = ? AND content LIKE ?
                    ORDER BY chunk_index ASC
                    LIMIT ?
                    """,
                    (course_id, f"%{query_text}%", max(1, limit)),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        chunk_id, course_id, file_id, chunk_index, source_page, source_section,
                        content, token_estimate, embedding_json, metadata_json, created_at, updated_at
                    FROM knowledge_chunks
                    WHERE course_id = ?
                    ORDER BY chunk_index ASC
                    LIMIT ?
                    """,
                    (course_id, max(1, limit)),
                ).fetchall()
        return [
            {
                "chunkId": str(row["chunk_id"]),
                "courseId": str(row["course_id"]),
                "fileId": str(row["file_id"]),
                "chunkIndex": int(row["chunk_index"]),
                "sourcePage": int(row["source_page"]),
                "sourceSection": str(row["source_section"]),
                "content": str(row["content"]),
                "tokenEstimate": int(row["token_estimate"]),
                "embedding": json.loads(row["embedding_json"] or "[]"),
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in rows
        ]

    def list_chunks_for_retrieval(self, *, course_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    chunk_id, course_id, file_id, chunk_index, source_page, source_section,
                    content, token_estimate, embedding_json, metadata_json, created_at, updated_at
                FROM knowledge_chunks
                WHERE course_id = ?
                ORDER BY chunk_index ASC
                LIMIT ?
                """,
                (course_id, max(1, limit)),
            ).fetchall()
        return [
            {
                "chunkId": str(row["chunk_id"]),
                "courseId": str(row["course_id"]),
                "fileId": str(row["file_id"]),
                "chunkIndex": int(row["chunk_index"]),
                "sourcePage": int(row["source_page"]),
                "sourceSection": str(row["source_section"]),
                "content": str(row["content"]),
                "tokenEstimate": int(row["token_estimate"]),
                "embedding": json.loads(row["embedding_json"] or "[]"),
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "createdAt": str(row["created_at"]),
                "updatedAt": str(row["updated_at"]),
            }
            for row in rows
        ]

    def list_chunk_texts(self, *, course_id: str, limit: int = 0) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            if limit > 0:
                rows = connection.execute(
                    """
                    SELECT chunk_id, content
                    FROM knowledge_chunks
                    WHERE course_id = ?
                    ORDER BY chunk_index ASC
                    LIMIT ?
                    """,
                    (course_id, int(limit)),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT chunk_id, content
                    FROM knowledge_chunks
                    WHERE course_id = ?
                    ORDER BY chunk_index ASC
                    """,
                    (course_id,),
                ).fetchall()
        return [{"chunkId": str(row["chunk_id"]), "content": str(row["content"])} for row in rows]

    def update_chunk_embeddings(self, *, embeddings: list[tuple[str, list[float]]]) -> int:
        if not embeddings:
            return 0
        now = _utcnow()
        with closing(self._connect()) as connection:
            for chunk_id, vector in embeddings:
                connection.execute(
                    """
                    UPDATE knowledge_chunks
                    SET embedding_json = ?, updated_at = ?
                    WHERE chunk_id = ?
                    """,
                    (json.dumps(vector, ensure_ascii=False), now, chunk_id),
                )
            connection.commit()
        return len(embeddings)
