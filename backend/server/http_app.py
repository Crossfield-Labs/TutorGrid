from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.knowledge.service import KnowledgeBaseService
from backend.learning_profile.service import LearningProfileService
from backend.rag.service import RagService
from backend.server.chat_api import router as chat_router


knowledge_service = KnowledgeBaseService()
rag_service = RagService(knowledge_service=knowledge_service)
profile_service = LearningProfileService()

app = FastAPI(title="TutorGrid Backend B API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
profile_router = APIRouter(prefix="/api/profile", tags=["profile"])


class CreateCourseRequest(BaseModel):
    name: str
    description: str = ""


class RagQueryRequest(BaseModel):
    course_id: str
    question: str
    limit: int = Field(default=5, ge=1, le=20)


@knowledge_router.get("/courses")
async def list_courses(limit: int = 50) -> list[dict[str, Any]]:
    return knowledge_service.list_courses(limit=max(1, limit))


@knowledge_router.post("/courses")
async def create_course(payload: CreateCourseRequest) -> dict[str, Any]:
    try:
        return knowledge_service.create_course(name=payload.name, description=payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@knowledge_router.post("/courses/{course_id}/files")
async def upload_course_file(
    course_id: str,
    file: UploadFile = File(...),
    chunk_size: int = Form(900),
) -> dict[str, Any]:
    raw_dir = Path("scratch") / "uploads"
    raw_dir.mkdir(parents=True, exist_ok=True)
    file_path = raw_dir / file.filename
    with file_path.open("wb") as stream:
        stream.write(await file.read())
    try:
        return knowledge_service.ingest_file(
            course_id=course_id,
            file_path=str(file_path),
            file_name=file.filename,
            chunk_size=chunk_size,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@knowledge_router.get("/courses/{course_id}/files")
async def list_course_files(course_id: str, limit: int = 200) -> list[dict[str, Any]]:
    try:
        return knowledge_service.list_files(course_id=course_id, limit=max(1, limit))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@knowledge_router.post("/rag/query")
async def rag_query(payload: RagQueryRequest) -> dict[str, Any]:
    try:
        return await rag_service.query(course_id=payload.course_id, question=payload.question, limit=payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@profile_router.get("")
async def get_profile(user_id: str = "default", course_id: str = "", limit: int = 100) -> dict[str, Any]:
    return profile_service.get_profile_summary(user_id=user_id, course_id=course_id, limit=limit)


@profile_router.get("/mastery")
async def get_mastery(user_id: str = "default", course_id: str = "", limit: int = 200) -> dict[str, Any]:
    return profile_service.list_l4_mastery(user_id=user_id, course_id=course_id, limit=limit)


app.include_router(knowledge_router)
app.include_router(profile_router)
