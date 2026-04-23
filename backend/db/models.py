from __future__ import annotations

from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    node_id: Mapped[str] = mapped_column(String, nullable=False)
    runner: Mapped[str] = mapped_column(String, nullable=False)
    workspace: Mapped[str] = mapped_column(String, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    stop_reason: Mapped[str] = mapped_column(String, nullable=False)
    latest_summary: Mapped[str] = mapped_column(Text, nullable=False)
    latest_artifact_summary: Mapped[str] = mapped_column(Text, nullable=False)
    permission_summary: Mapped[str] = mapped_column(Text, nullable=False)
    session_info_summary: Mapped[str] = mapped_column(Text, nullable=False)
    mcp_status_summary: Mapped[str] = mapped_column(Text, nullable=False)
    active_worker: Mapped[str] = mapped_column(String, nullable=False)
    active_session_mode: Mapped[str] = mapped_column(String, nullable=False)
    active_worker_profile: Mapped[str] = mapped_column(String, nullable=False)
    active_worker_task_id: Mapped[str] = mapped_column(String, nullable=False)
    active_worker_can_interrupt: Mapped[bool] = mapped_column(nullable=False, default=False)
    awaiting_input: Mapped[bool] = mapped_column(nullable=False, default=False)
    pending_user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    completed_at: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)


class SessionSnapshotModel(Base):
    __tablename__ = "session_snapshots"
    __table_args__ = (UniqueConstraint("session_id", "snapshot_version", name="uq_session_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class SessionMessageModel(Base):
    __tablename__ = "session_messages"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_session_message"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    message_type: Mapped[str] = mapped_column(String, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    tool_call_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class SessionErrorModel(Base):
    __tablename__ = "session_errors"
    __table_args__ = (UniqueConstraint("session_id", "seq", "message", name="uq_session_error"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    error_layer: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    retryable: Mapped[bool] = mapped_column(nullable=False, default=False)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    worker: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class SessionArtifactModel(Base):
    __tablename__ = "session_artifacts"
    __table_args__ = (UniqueConstraint("session_id", "path", name="uq_session_artifact"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class MemoryCompactionModel(Base):
    __tablename__ = "memory_compactions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    facts_json: Mapped[list] = mapped_column(JSON, nullable=False)
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class MemoryDocumentModel(Base):
    __tablename__ = "memory_documents"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    embedding_json: Mapped[list] = mapped_column(JSON, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class LearningProfileModel(Base):
    __tablename__ = "learning_profiles"

    profile_level: Mapped[str] = mapped_column(String, primary_key=True)
    profile_key: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    workspace: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    facts_json: Mapped[list] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class LearningPushRecordModel(Base):
    __tablename__ = "learning_push_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    profile_level: Mapped[str] = mapped_column(String, nullable=False)
    profile_key: Mapped[str] = mapped_column(String, nullable=False)
    push_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
