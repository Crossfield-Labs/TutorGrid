from backend.agent.main_agent import ChatAgent
from backend.agent.tools import _normalize_tavily_results, build_tools


class _UnusedRagService:
    pass


def _agent() -> ChatAgent:
    return object.__new__(ChatAgent)


def test_time_sensitive_question_prefers_tavily() -> None:
    agent = _agent()

    assert agent._should_use_tavily_first(message="请查一下今天大模型最新新闻", allowed_tools={"rag", "tavily"})
    assert not agent._should_use_rag_first(
        message="请查一下今天大模型最新新闻",
        course_id="course-001",
        allowed_tools={"rag", "tavily"},
    )


def test_f03_demo_query_prefers_tavily() -> None:
    agent = _agent()

    assert agent._should_use_tavily_first(message="最新的正则化方法有哪些", allowed_tools={"rag", "tavily"})
    assert not agent._should_use_rag_first(
        message="最新的正则化方法有哪些",
        course_id="course_datamining",
        allowed_tools={"rag", "tavily"},
    )


def test_course_question_prefers_rag_when_course_id_exists() -> None:
    agent = _agent()

    assert agent._should_use_rag_first(
        message="解释一下课程里的注意力机制",
        course_id="course-001",
        allowed_tools={"rag", "tavily"},
    )
    assert not agent._should_use_tavily_first(message="解释一下课程里的注意力机制", allowed_tools={"rag", "tavily"})


def test_direct_llm_path_when_no_tool_matches() -> None:
    agent = _agent()

    assert not agent._should_use_rag_first(message="帮我写一个学习计划", course_id="", allowed_tools={"rag", "tavily"})
    assert not agent._should_use_tavily_first(message="帮我写一个学习计划", allowed_tools={"rag", "tavily"})


def test_enabled_tools_are_respected_by_routing() -> None:
    agent = _agent()

    assert not agent._should_use_tavily_first(message="今天有哪些最新趋势", allowed_tools={"rag"})
    assert not agent._should_use_rag_first(message="解释课程概念", course_id="course-001", allowed_tools={"tavily"})


def test_build_tools_respects_enabled_tool_list() -> None:
    rag_only = build_tools(rag_service=_UnusedRagService(), enabled_tools=["rag"])
    tavily_only = build_tools(rag_service=_UnusedRagService(), enabled_tools=["tavily"])
    all_tools = build_tools(rag_service=_UnusedRagService(), enabled_tools=["rag", "tavily"])

    assert [tool["function"]["name"] for tool in rag_only] == ["rag_query"]
    assert [tool["function"]["name"] for tool in tavily_only] == ["tavily_search"]
    assert [tool["function"]["name"] for tool in all_tools] == ["rag_query", "tavily_search"]


def test_tavily_result_normalization_keeps_source_urls() -> None:
    results = _normalize_tavily_results(
        {
            "results": [
                {
                    "title": "Regularization survey",
                    "url": "https://example.edu/regularization",
                    "content": "A short summary",
                    "score": 0.91,
                },
                {"title": "No URL", "content": "ignored"},
            ]
        }
    )

    assert results == [
        {
            "title": "Regularization survey",
            "url": "https://example.edu/regularization",
            "content": "A short summary",
            "score": 0.91,
        }
    ]


def test_agent_extracts_tavily_results_for_frontend_citations() -> None:
    agent = _agent()

    results = agent._search_results_from_tool_result(
        {
            "results": [
                {
                    "title": "AI news",
                    "url": "https://example.com/ai-news",
                    "content": "Fresh information",
                    "score": 0.8,
                }
            ]
        }
    )

    assert results[0]["url"] == "https://example.com/ai-news"
    assert results[0]["title"] == "AI news"


def test_system_prompt_contains_required_copilot_positioning() -> None:
    agent = _agent()
    messages = agent._build_messages(message="你好", course_id="course-001", context={"recent_paragraphs": ["第一段"]})

    system_prompt = messages[0]["content"]
    assert "你是学生的 Copilot 副驾驶" in system_prompt
    assert "不是替代学习" in system_prompt
    assert "rag_query" in system_prompt
    assert "tavily_search" in system_prompt
    assert "course-001" in system_prompt
    assert "第一段" in system_prompt