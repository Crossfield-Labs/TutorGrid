from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import (
    get_runtime_config_view,
    update_langsmith_config,
    update_planner_config,
    update_search_config,
)
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
        "http://127.0.0.1:4399",
        "http://localhost:4399",
        "app://./",  # Electron 打包后协议
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
profile_router = APIRouter(prefix="/api/profile", tags=["profile"])
config_router = APIRouter(prefix="/api/config", tags=["config"])


class CreateCourseRequest(BaseModel):
    name: str
    description: str = ""


class LocalIngestRequest(BaseModel):
    file_path: str
    file_name: str = ""
    chunk_size: int = Field(default=900, ge=200, le=4000)


class RagQueryRequest(BaseModel):
    course_id: str
    question: str
    limit: int = Field(default=5, ge=1, le=20)


class PlannerConfigPayload(BaseModel):
    provider: str = "openai_compat"
    model: str = ""
    apiKey: str = ""
    apiBase: str = ""


class LangSmithConfigPayload(BaseModel):
    enabled: bool = False
    project: str = "pc-orchestrator-core"
    apiKey: str = ""
    apiUrl: str = ""


class SearchConfigPayload(BaseModel):
    tavilyApiKey: str = ""


class RuntimeConfigPayload(BaseModel):
    planner: PlannerConfigPayload = Field(default_factory=PlannerConfigPayload)
    langsmith: LangSmithConfigPayload = Field(default_factory=LangSmithConfigPayload)
    search: SearchConfigPayload = Field(default_factory=SearchConfigPayload)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok"}


@config_router.get("")
async def get_config() -> dict[str, Any]:
    return get_runtime_config_view()


@config_router.put("")
async def put_config(payload: RuntimeConfigPayload) -> dict[str, Any]:
    update_planner_config(
        provider=payload.planner.provider.strip() or "openai_compat",
        model=payload.planner.model.strip(),
        api_key=payload.planner.apiKey.strip(),
        api_base=payload.planner.apiBase.strip(),
    )
    update_langsmith_config(
        enabled=payload.langsmith.enabled,
        project=payload.langsmith.project.strip() or "pc-orchestrator-core",
        api_key=payload.langsmith.apiKey.strip(),
        api_url=payload.langsmith.apiUrl.strip(),
    )
    update_search_config(
        tavily_api_key=payload.search.tavilyApiKey.strip(),
    )
    return get_runtime_config_view()


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


@knowledge_router.post("/courses/{course_id}/files/import-local")
async def import_local_course_file(course_id: str, payload: LocalIngestRequest) -> dict[str, Any]:
    try:
        return knowledge_service.ingest_file(
            course_id=course_id,
            file_path=payload.file_path,
            file_name=payload.file_name or Path(payload.file_path).name,
            chunk_size=payload.chunk_size,
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
app.include_router(config_router)
