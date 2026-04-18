from __future__ import annotations

try:
    from langchain_core.tools import StructuredTool
except ImportError:  # pragma: no cover
    StructuredTool = None

from orchestrator.tools.delegate import delegate_task
from orchestrator.tools.filesystem import list_files, read_file
from orchestrator.tools.shell import run_shell
from orchestrator.tools.user_prompt import build_await_user_tool
from orchestrator.tools.web import web_fetch


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

    return [
        StructuredTool.from_function(coroutine=_list_files, name="list_files", description="List files in the workspace."),
        StructuredTool.from_function(coroutine=_read_file, name="read_file", description="Read a text file."),
        StructuredTool.from_function(coroutine=_run_shell, name="run_shell", description="Run a shell command."),
        StructuredTool.from_function(coroutine=web_fetch, name="web_fetch", description="Fetch a public web page."),
        StructuredTool.from_function(coroutine=await_user, name="await_user", description="Ask the user for input."),
        StructuredTool.from_function(coroutine=_delegate_task, name="delegate_task", description="Delegate work to a worker."),
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
