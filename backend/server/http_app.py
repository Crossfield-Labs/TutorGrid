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
from backend.server.chat_api import router as chat_router, set_chat_service
from backend.study_cards.service import StudyCardGenerationError, StudyCardService
from backend.workspace_meta import WorkspaceMetaService
from backend.chats import ChatService


knowledge_service = KnowledgeBaseService()
rag_service = RagService(knowledge_service=knowledge_service)
profile_service = LearningProfileService()
study_card_service = StudyCardService()
DB_PATH = Path(__file__).resolve().parents[2] / "scratch" / "storage" / "orchestrator.sqlite3"
workspace_meta_service = WorkspaceMetaService(db_path=DB_PATH)
chat_service = ChatService(db_path=DB_PATH)
set_chat_service(chat_service)  # 让 chat_api 的 SSE 端点能写库

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
study_router = APIRouter(prefix="/api/study", tags=["study"])
config_router = APIRouter(prefix="/api/config", tags=["config"])
workspace_router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
hyperdoc_router = APIRouter(prefix="/api/hyperdocs", tags=["hyperdocs"])
chats_router = APIRouter(prefix="/api/chats", tags=["chats"])


class CreateChatSessionRequest(BaseModel):
    title: str = ""


class RenameChatSessionRequest(BaseModel):
    title: str


class AppendChatMessageRequest(BaseModel):
    role: str  # user | ai | system
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceAppearance(BaseModel):
    topBarBg: str = ""    # AppBar 背景图 URL（可空）
    pageBg: str = ""      # 整页背景图 URL（可空）
    sidebarColor: str = ""  # Sidebar 色块（可空）


class CreateWorkspaceRequest(BaseModel):
    name: str
    fsRoot: str  # Electron 选定的本地目录绝对路径
    appearance: WorkspaceAppearance = Field(default_factory=WorkspaceAppearance)


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    fsRoot: str | None = None
    appearance: WorkspaceAppearance | None = None


class CreateHyperdocMetaRequest(BaseModel):
    title: str
    fileRelPath: str


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


class StudyCardsRequest(BaseModel):
    sourceText: str
    courseId: str = ""
    docId: str = ""
    language: str = "zh-CN"


class MasteryUpdateRequest(BaseModel):
    courseId: str
    knowledgePoint: str
    mastery: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlannerConfigPayload(BaseModel):
    provider: str = "openai_compat"
    model: str = ""
    apiKey: str = ""
    apiBase: str = ""
    providerOptions: dict[str, Any] = Field(default_factory=dict)


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
        provider_options=payload.planner.providerOptions,
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


@knowledge_router.post("/courses/{course_id}/reindex")
async def reindex_course(course_id: str, batch_size: int = 64) -> dict[str, Any]:
    try:
        return knowledge_service.reembed_course(course_id=course_id, batch_size=batch_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@profile_router.get("")
async def get_profile(user_id: str = "default", course_id: str = "", limit: int = 100) -> dict[str, Any]:
    return profile_service.get_profile_summary(user_id=user_id, course_id=course_id, limit=limit)


@profile_router.get("/mastery")
async def get_mastery(user_id: str = "default", course_id: str = "", limit: int = 200) -> dict[str, Any]:
    return profile_service.list_l4_mastery(user_id=user_id, course_id=course_id, limit=limit)


@profile_router.post("/mastery")
async def update_mastery(payload: MasteryUpdateRequest, user_id: str = "default") -> dict[str, Any]:
    try:
        return profile_service.upsert_l4_mastery(
            user_id=user_id,
            course_id=payload.courseId,
            knowledge_point=payload.knowledgePoint,
            mastery=payload.mastery,
            confidence=payload.confidence,
            evidence=payload.evidence,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@study_router.post("/cards")
async def generate_study_cards(payload: StudyCardsRequest) -> dict[str, Any]:
    try:
        return await study_card_service.generate(
            source_text=payload.sourceText,
            course_id=payload.courseId,
            doc_id=payload.docId,
            language=payload.language,
        )
    except StudyCardGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@workspace_router.get("")
async def list_workspaces() -> list[dict[str, Any]]:
    return workspace_meta_service.list_workspaces()


@workspace_router.get("/{workspace_id}")
async def get_workspace(workspace_id: str) -> dict[str, Any]:
    item = workspace_meta_service.get_workspace(workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return item


@workspace_router.post("")
async def create_workspace(payload: CreateWorkspaceRequest) -> dict[str, Any]:
    try:
        return workspace_meta_service.create_workspace(
            name=payload.name,
            fs_root=payload.fsRoot,
            appearance=payload.appearance.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@workspace_router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: str, payload: UpdateWorkspaceRequest
) -> dict[str, Any]:
    appearance_dict = payload.appearance.model_dump() if payload.appearance else None
    item = workspace_meta_service.update_workspace(
        workspace_id,
        name=payload.name,
        fs_root=payload.fsRoot,
        appearance=appearance_dict,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return item


@workspace_router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict[str, Any]:
    deleted = workspace_meta_service.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return {"status": "ok", "id": workspace_id}


@workspace_router.get("/{workspace_id}/hyperdocs")
async def list_workspace_hyperdocs(workspace_id: str) -> list[dict[str, Any]]:
    try:
        return workspace_meta_service.list_hyperdocs(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@workspace_router.post("/{workspace_id}/hyperdocs")
async def create_workspace_hyperdoc(
    workspace_id: str, payload: CreateHyperdocMetaRequest
) -> dict[str, Any]:
    try:
        return workspace_meta_service.create_hyperdoc(
            workspace_id=workspace_id,
            title=payload.title,
            file_rel_path=payload.fileRelPath,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@hyperdoc_router.delete("/{hyperdoc_id}")
async def delete_hyperdoc_meta(hyperdoc_id: str) -> dict[str, Any]:
    deleted = workspace_meta_service.delete_hyperdoc(hyperdoc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Hyperdoc 不存在")
    return {"status": "ok", "id": hyperdoc_id}


# -------- Chat 会话与消息（Step 2） --------

@hyperdoc_router.get("/{hyperdoc_id}/chats")
async def list_hyperdoc_chats(hyperdoc_id: str) -> list[dict[str, Any]]:
    return chat_service.list_sessions(hyperdoc_id)


@hyperdoc_router.post("/{hyperdoc_id}/chats")
async def create_hyperdoc_chat(
    hyperdoc_id: str, payload: CreateChatSessionRequest
) -> dict[str, Any]:
    try:
        return chat_service.create_session(hyperdoc_id=hyperdoc_id, title=payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@chats_router.get("/{session_id}")
async def get_chat_session(session_id: str) -> dict[str, Any]:
    item = chat_service.get_session(session_id)
    if item is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return item


@chats_router.put("/{session_id}")
async def rename_chat_session(
    session_id: str, payload: RenameChatSessionRequest
) -> dict[str, Any]:
    item = chat_service.rename_session(session_id, payload.title)
    if item is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return item


@chats_router.delete("/{session_id}")
async def delete_chat_session(session_id: str) -> dict[str, Any]:
    deleted = chat_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "ok", "id": session_id}


@chats_router.get("/{session_id}/messages")
async def list_chat_messages(session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    return chat_service.list_messages(session_id, limit=limit)


@chats_router.post("/{session_id}/messages")
async def append_chat_message(
    session_id: str, payload: AppendChatMessageRequest
) -> dict[str, Any]:
    """前端兜底用（一般 SSE 端点会自动写）。"""
    try:
        return chat_service.append_message(
            session_id=session_id,
            role=payload.role,
            content=payload.content,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app.include_router(knowledge_router)
app.include_router(profile_router)
app.include_router(study_router)
app.include_router(config_router)
app.include_router(workspace_router)
app.include_router(hyperdoc_router)
app.include_router(chats_router)
