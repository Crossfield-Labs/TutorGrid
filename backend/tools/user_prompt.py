from __future__ import annotations

from typing import Awaitable, Callable

AwaitUserFn = Callable[[str, str | None], Awaitable[str]]


def build_await_user_tool(await_user_fn: AwaitUserFn) -> AwaitUserFn:
    return await_user_fn

