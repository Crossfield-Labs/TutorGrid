from __future__ import annotations

from backend.study_cards.service import parse_study_cards_response


def test_parse_study_cards_response_extracts_quiz_and_flashcards() -> None:
    payload = """
    {
      "quiz": {
        "question": "过拟合通常表现为什么？",
        "options": ["训练集差测试集好", "训练集好测试集差", "两者都差", "无影响"],
        "answer": 1,
        "explanation": "过拟合说明模型记住了训练数据，泛化能力弱。"
      },
      "flashcards": [
        {"front": "什么是过拟合？", "back": "训练集表现好但测试集表现差。"},
        {"front": "如何缓解？", "back": "正则化、更多数据、早停等。"}
      ]
    }
    """

    result = parse_study_cards_response(payload)

    assert result["quiz"]["answer"] == 1
    assert result["quiz"]["options"][1] == "训练集好测试集差"
    assert result["flashcards"][0]["front"] == "什么是过拟合？"


def test_parse_study_cards_response_rejects_incomplete_quiz() -> None:
    payload = '{"quiz": {"question": "x", "options": ["a"], "answer": 3}, "flashcards": []}'

    result = parse_study_cards_response(payload)

    assert result["quiz"] is None
    assert result["flashcards"] == []
