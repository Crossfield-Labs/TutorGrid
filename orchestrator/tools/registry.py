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

from orchestrator.tools.delegate import delegate_task
from orchestrator.tools.filesystem import list_files, read_file
from orchestrator.tools.shell import run_shell
from orchestrator.tools.user_prompt import build_await_user_tool
from orchestrator.tools.web import web_fetch


if BaseModel is not None and Field is not None:
    class ListFilesArgs(BaseModel):
        path: str = Field(default=".", description="Workspace-relative path to inspect.")


    class ReadFileArgs(BaseModel):
        path: str = Field(description="Workspace-relative text file path to read.")


    class RunShellArgs(BaseModel):
        command: str = Field(description="Focused shell command to execute in the workspace.")


    class AwaitUserArgs(BaseModel):
        message: str = Field(description="Question or prompt to show to the user.")
        input_mode: str = Field(default="text", description="Expected input mode, usually 'text'.")


    class DelegateTaskArgs(BaseModel):
        task: str = Field(description="Focused task to delegate to a stronger backend.")
        worker: str = Field(default="", description="Optional preferred worker: opencode, codex, or claude.")
        session_mode: str = Field(default="", description="Optional session mode: auto, new, resume, or fork.")
        session_key: str = Field(default="", description="Optional logical long-lived backend conversation key.")
        profile: str = Field(default="", description="Optional backend profile. For Claude: code, doc, study, or research.")


    class DelegateOpenCodeArgs(BaseModel):
        task: str = Field(description="Focused task to delegate to the OpenCode worker.")
        session_mode: str = Field(default="", description="Optional session mode. Usually keep this empty or use 'new'.")
        session_key: str = Field(default="", description="Optional logical backend conversation key.")
else:
    ListFilesArgs = ReadFileArgs = RunShellArgs = AwaitUserArgs = DelegateTaskArgs = DelegateOpenCodeArgs = None


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
        return await list_files(path if path != "." else workspace)

    async def _read_file(path: str) -> str:
        return await read_file(path)

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
            coroutine=_delegate_task,
            name="delegate_task",
            description="Delegate work to a stronger worker backend. Prefer opencode for edits, codex for analysis, and claude for richer documentation or research flows.",
            args_schema=DelegateTaskArgs,
        ),
        StructuredTool.from_function(
            coroutine=_delegate_opencode,
            name="delegate_opencode",
            description="Delegate work specifically to the OpenCode worker.",
            args_schema=DelegateOpenCodeArgs,
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
