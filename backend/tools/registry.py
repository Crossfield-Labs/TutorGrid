from __future__ import annotations

try:
    from langchain_core.tools import StructuredTool
except ImportError:  # pragma: no cover
    StructuredTool = None

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    BaseModel = None
    Field = None

from backend.tools.delegate import delegate_task
from backend.tools.database import query_database
from backend.tools.document import write_to_doc
from backend.tools.filesystem import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    write_file,
)
from backend.tools.shell import run_shell
from backend.tools.user_prompt import build_await_user_tool
from backend.tools.web import web_fetch


if BaseModel is not None and Field is not None:
    class ListFilesArgs(BaseModel):
        path: str = Field(default=".", description="Workspace-relative path to inspect.")


    class ReadFileArgs(BaseModel):
        path: str = Field(description="Workspace-relative text file path to read.")


    class WriteFileArgs(BaseModel):
        path: str = Field(description="Workspace-relative file path to write.")
        content: str = Field(description="Full UTF-8 content to write. Existing files are overwritten.")


    class EditFileArgs(BaseModel):
        path: str = Field(description="Workspace-relative file path to modify.")
        old: str = Field(description="Exact substring (with surrounding context) to replace.")
        new: str = Field(description="Replacement substring; pass empty string to delete the matched text.")
        occurrences: int = Field(default=1, description="Expected number of matches; 0 replaces every occurrence.")


    class GlobArgs(BaseModel):
        pattern: str = Field(description="Glob pattern relative to the workspace, e.g. 'backend/**/*.py'.")


    class GrepArgs(BaseModel):
        pattern: str = Field(description="Regular expression to search within files.")
        path: str = Field(default=".", description="Workspace-relative directory or file to scan.")
        include: str = Field(default="", description="Optional glob to narrow scanned files, e.g. '**/*.py'.")
        case_insensitive: bool = Field(default=False, description="Set true to ignore case while matching.")


    class RunShellArgs(BaseModel):
        command: str = Field(description="Focused shell command to execute in the workspace.")


    class AwaitUserArgs(BaseModel):
        message: str = Field(description="Question or prompt to show to the user.")
        input_mode: str = Field(default="text", description="Expected input mode, usually 'text'.")


    class DelegateTaskArgs(BaseModel):
        task: str = Field(description="Focused task to delegate to a stronger backend.")
        worker: str = Field(default="", description="Optional preferred worker: codex (default primary) or opencode.")
        session_mode: str = Field(default="", description="Session lifecycle: 'new' starts a fresh worker session, 'resume' continues an existing one (requires session_key with prior history), 'continue' picks up the worker's most recent session.")
        session_key: str = Field(default="", description="Stable logical name for a long-running collaboration thread with one worker (e.g. 'svm_train'). Reuse the same key across delegate calls to keep context.")
        profile: str = Field(default="", description="Reserved for future worker-specific profiles. Leave empty.")


    class DelegateCodexArgs(BaseModel):
        task: str = Field(description="Focused task to delegate to the Codex worker (primary coding/reasoning backend).")
        session_mode: str = Field(default="", description="Use 'resume' with the same session_key to continue an in-flight Codex conversation; otherwise leave empty or 'new'.")
        session_key: str = Field(default="", description="Stable logical name for the long-running Codex thread. Reuse to keep context.")


    class DelegateOpenCodeArgs(BaseModel):
        task: str = Field(description="Focused task to delegate to the OpenCode worker.")
        session_mode: str = Field(default="", description="Use 'resume' with the same session_key to continue, 'continue' to pick up the most recent OpenCode session, or leave empty for a new one.")
        session_key: str = Field(default="", description="Stable logical name for the long-running OpenCode thread.")


    class WriteToDocArgs(BaseModel):
        content: str = Field(description="Markdown content to insert into the bound hyperdoc.")
        kind: str = Field(default="report", description="Block kind: report | explanation | summary | code_output | citation.")
        title: str = Field(default="", description="Optional heading shown above the inserted block.")
        placement: str = Field(default="append", description="Where to insert: append (end of doc), replace_section (overwrite anchor section), inline_after (after anchor).")
        anchor: str = Field(default="", description="Optional node id used for replace_section / inline_after.")
        doc_id: str = Field(default="", description="Override the bound doc_id; leave empty to write to the task's hyperdoc.")


    class QueryDatabaseArgs(BaseModel):
        table: str = Field(
            description="Database view to inspect. Supported: sessions, session_messages, session_errors, session_artifacts, memory_documents, learning_profiles, learning_push_records."
        )
        session_id: str = Field(default="", description="Optional session id filter for session-scoped tables.")
        profile_level: str = Field(default="", description="Optional profile level filter for learning_profiles.")
        limit: int = Field(default=20, description="Maximum number of rows to return.")
else:
    ListFilesArgs = ReadFileArgs = WriteFileArgs = EditFileArgs = GlobArgs = GrepArgs = None
    RunShellArgs = AwaitUserArgs = None
    DelegateTaskArgs = DelegateCodexArgs = DelegateOpenCodeArgs = None
    WriteToDocArgs = QueryDatabaseArgs = None


def build_langchain_tools(
    *,
    workspace: str,
    shell_timeout_seconds: int,
    await_user_fn,
    worker_registry=None,
    session=None,
) -> list[object]:
    if StructuredTool is None:
        return []

    async def _list_files(path: str = ".") -> str:
        return await list_files(path or ".", workspace=workspace)

    async def _read_file(path: str) -> str:
        return await read_file(path, workspace=workspace)

    async def _write_file(path: str, content: str) -> str:
        return await write_file(path, content, workspace=workspace)

    async def _edit_file(path: str, old: str, new: str, occurrences: int = 1) -> str:
        return await edit_file(path, old, new, workspace=workspace, occurrences=occurrences)

    async def _glob(pattern: str) -> str:
        return await glob_files(pattern, workspace=workspace)

    async def _grep(
        pattern: str,
        path: str = ".",
        include: str = "",
        case_insensitive: bool = False,
    ) -> str:
        return await grep_files(
            pattern,
            path=path,
            workspace=workspace,
            include=include,
            case_insensitive=case_insensitive,
        )

    async def _run_shell(command: str) -> str:
        return await run_shell(command, timeout_seconds=shell_timeout_seconds)

    await_user = build_await_user_tool(await_user_fn)

    async def _delegate_task(
        task: str,
        worker: str = "",
        session_mode: str = "",
        session_key: str = "",
        profile: str = "",
    ) -> str:
        if worker_registry is None:
            return "Error: worker registry is not configured."
        return await delegate_task(
            task=task,
            worker=worker,
            session_mode=session_mode,
            session_key=session_key,
            profile=profile,
            workspace=workspace,
            worker_registry=worker_registry,
            session=session,
        )

    async def _delegate_codex(task: str, session_mode: str = "", session_key: str = "") -> str:
        if worker_registry is None:
            return "Error: worker registry is not configured."
        return await delegate_task(
            task=task,
            worker="codex",
            session_mode=session_mode,
            session_key=session_key,
            profile="",
            workspace=workspace,
            worker_registry=worker_registry,
            session=session,
        )

    async def _delegate_opencode(task: str, session_mode: str = "", session_key: str = "") -> str:
        if worker_registry is None:
            return "Error: worker registry is not configured."
        return await delegate_task(
            task=task,
            worker="opencode",
            session_mode=session_mode,
            session_key=session_key,
            profile="",
            workspace=workspace,
            worker_registry=worker_registry,
            session=session,
        )

    async def _write_to_doc(
        content: str,
        kind: str = "report",
        title: str = "",
        placement: str = "append",
        anchor: str = "",
        doc_id: str = "",
    ) -> str:
        return await write_to_doc(
            session,
            content=content,
            doc_id=doc_id,
            kind=kind,
            title=title,
            placement=placement,
            anchor=anchor,
        )

    async def _query_database(table: str, session_id: str = "", profile_level: str = "", limit: int = 20) -> str:
        return await query_database(
            table=table,
            session_id=session_id,
            profile_level=profile_level,
            limit=limit,
        )

    return [
        StructuredTool.from_function(
            coroutine=_list_files,
            name="list_files",
            description="List files in the workspace or under a subdirectory.",
            args_schema=ListFilesArgs,
        ),
        StructuredTool.from_function(
            coroutine=_read_file,
            name="read_file",
            description="Read a UTF-8 text file from the workspace.",
            args_schema=ReadFileArgs,
        ),
        StructuredTool.from_function(
            coroutine=_write_file,
            name="write_file",
            description="Create or overwrite a workspace text file with the provided content.",
            args_schema=WriteFileArgs,
        ),
        StructuredTool.from_function(
            coroutine=_edit_file,
            name="edit_file",
            description="Replace an exact substring inside a workspace file. Provide enough surrounding context to make 'old' unique.",
            args_schema=EditFileArgs,
        ),
        StructuredTool.from_function(
            coroutine=_glob,
            name="glob",
            description="List workspace files that match a glob pattern (e.g. 'backend/**/*.py').",
            args_schema=GlobArgs,
        ),
        StructuredTool.from_function(
            coroutine=_grep,
            name="grep",
            description="Search file contents in the workspace with a regular expression.",
            args_schema=GrepArgs,
        ),
        StructuredTool.from_function(
            coroutine=_run_shell,
            name="run_shell",
            description="Run a focused shell command in the workspace.",
            args_schema=RunShellArgs,
        ),
        StructuredTool.from_function(coroutine=web_fetch, name="web_fetch", description="Fetch a public web page."),
        StructuredTool.from_function(
            coroutine=await_user,
            name="await_user",
            description="Ask the user for a decision or clarification instead of guessing.",
            args_schema=AwaitUserArgs,
        ),
        StructuredTool.from_function(
            coroutine=_delegate_codex,
            name="delegate_codex",
            description="Delegate to the primary Codex worker. Codex is the strongest coding/reasoning backend; prefer it for implementation, refactoring, debugging, code review, and structured analysis. Reuse the same session_key with session_mode='resume' to keep a multi-turn collaboration with Codex.",
            args_schema=DelegateCodexArgs,
        ),
        StructuredTool.from_function(
            coroutine=_delegate_opencode,
            name="delegate_opencode",
            description="Delegate to the OpenCode worker (equivalent capability to Codex; use it as a fallback or to parallelize independent subtasks). Reuse the same session_key with session_mode='resume' or 'continue' to keep context.",
            args_schema=DelegateOpenCodeArgs,
        ),
        StructuredTool.from_function(
            coroutine=_delegate_task,
            name="delegate_task",
            description="Generic delegation tool. Prefer the explicit delegate_codex / delegate_opencode tools; use this only when you need to pass a non-default profile or you have not decided which worker yet.",
            args_schema=DelegateTaskArgs,
        ),
        StructuredTool.from_function(
            coroutine=_write_to_doc,
            name="write_to_doc",
            description="Insert an AI-authored block (Markdown) into the bound hyperdoc as the task's deliverable. Use this for the final report, an explanation segment, or a result summary that the user should see in their document.",
            args_schema=WriteToDocArgs,
        ),
        StructuredTool.from_function(
            coroutine=_query_database,
            name="query_database",
            description="Inspect persisted session, memory, and learning-profile tables through the ORM-backed SQLite store.",
            args_schema=QueryDatabaseArgs,
        ),
    ]


def build_tool_map(tools: list[object]) -> dict[str, object]:
    tool_map: dict[str, object] = {}
    for tool in tools:
        name = getattr(tool, "name", "")
        if name:
            tool_map[str(name)] = tool
    return tool_map


def build_tool_definitions(tools: list[object]) -> list[dict[str, object]]:
    definitions: list[dict[str, object]] = []
    for tool in tools:
        name = getattr(tool, "name", "")
        description = getattr(tool, "description", "")
        args_schema = getattr(tool, "args_schema", None)
        parameters = {"type": "object", "properties": {}, "required": []}
        if args_schema is not None and hasattr(args_schema, "model_json_schema"):
            schema = args_schema.model_json_schema()
            if isinstance(schema, dict):
                parameters = schema
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": str(name),
                    "description": str(description),
                    "parameters": parameters,
                },
            }
        )
    return definitions


