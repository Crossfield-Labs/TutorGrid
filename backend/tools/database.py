from __future__ import annotations

from backend.db.inspector import DatabaseInspector


async def query_database(
    table: str,
    session_id: str = "",
    profile_level: str = "",
    limit: int = 20,
) -> str:
    inspector = DatabaseInspector()
    try:
        return inspector.query_json(
            table=table,
            session_id=session_id,
            profile_level=profile_level,
            limit=max(1, min(limit, 100)),
        )
    except ValueError as exc:
        return f"Error: {exc}"
