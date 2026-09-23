"""Тесты объяснения рекомендаций: шаблонный фолбэк и бюджет времени.

ТЗ: "Допустимая задержка: ... AI-рекомендация до 10 секунд" — на весь ответ, а шагов
может быть до трёх, поэтому бюджет на agentic-LLM должен быть общим, а не по шагу
(иначе 3 шага × до 8с каждый = до 24с). Проверяем, что при исчерпанном бюджете
явно не пытаемся звать LLM и мгновенно получаем шаблон, а не зависаем."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import explain
from app.explain import build_rationale


@pytest.fixture(autouse=True)
def clear_ai_cache():
    explain._cache.clear()
    explain._request_times.clear()
    explain._inflight.clear()

_STEP = {
    "event": {"title": "Test Event", "event_id": "EV_TEST"},
    "skills": [
        {
            "skill_id": "SK_X",
            "current": 1,
            "required": 3,
            "gap": 2,
            "critical": True,
            "history": {"completed": 0, "declined": 1, "no_show": 0, "dropped": 0},
            "was_avoided_before": False,
            "alternative_events": [],
        }
    ],
}


def test_no_api_key_falls_back_to_template(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = build_rationale("Senior", _STEP, "ru", "Тест Тестов")
    assert result["source"] == "template"
    assert "SK_X" in result["text"]


def test_template_uses_skill_name_when_available(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    step = {**_STEP, "skills": [{**_STEP["skills"][0], "skill_name": "System Design"}]}
    result = build_rationale("Senior", step, "ru", "Тест Тестов")
    assert "System Design" in result["text"]
    assert "SK_X" not in result["text"]


def test_expired_deadline_falls_back_instantly(monkeypatch):
    """Даже с (гипотетически) валидным ключом — если общий бюджет времени уже
    исчерпан, вызов LLM не делается вообще, и мы мгновенно получаем шаблон."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-would-be-valid-but-budget-is-gone")
    already_expired = time.monotonic() - 1.0

    start = time.monotonic()
    result = build_rationale("Senior", _STEP, "ru", "Тест Тестов", deadline=already_expired)
    elapsed = time.monotonic() - start

    assert result["source"] == "template"
    assert elapsed < 1.0, f"должно быть мгновенно (бюджет исчерпан), а заняло {elapsed:.2f}с"


def test_shared_deadline_bounds_total_time_for_three_steps(monkeypatch):
    """Имитация страницы сотрудника с 3 рекомендованными шагами: общий бюджет 8с
    на все три, а не 8с на каждый (иначе было бы до 24с — нарушение ТЗ)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-invalid-but-syntactically-present")
    deadline = time.monotonic() + 0.01  # бюджет почти сразу истечёт

    start = time.monotonic()
    for _ in range(3):
        build_rationale("Senior", _STEP, "ru", "Тест Тестов", deadline=deadline)
    elapsed = time.monotonic() - start

    assert elapsed < 2.0, f"3 шага с общим бюджетом не должны занимать заметное время, заняло {elapsed:.2f}с"


def fake_client(monkeypatch, create):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.chat.completions.create = create

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return client

    monkeypatch.setattr("openai.AsyncOpenAI", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    return client


def test_slow_provider_is_cancelled_within_deadline(monkeypatch):
    cancelled = []

    async def slow_request(**kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    fake_client(monkeypatch, slow_request)
    started = time.monotonic()
    answer = build_rationale("Senior", _STEP, "ru", "", deadline=started + 0.7)
    assert answer["source"] == "template"
    assert cancelled == [True]
    assert time.monotonic() - started < 1.5


def test_ai_text_without_history_tool_is_not_presented_as_grounded(monkeypatch):
    message = SimpleNamespace(content="An unsupported claim", tool_calls=None)
    create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")]))
    fake_client(monkeypatch, create)
    answer = build_rationale("Senior", _STEP, "en", "")
    assert answer["source"] == "template"


def test_successful_tools_are_traced_cached_and_invalidated_by_changed_facts(monkeypatch):
    from openai.types.chat import ChatCompletionMessage

    tool_message = ChatCompletionMessage(role="assistant", content=None, tool_calls=[{
        "id": "history_call", "type": "function",
        "function": {"name": "get_skill_history", "arguments": '{"skill_id":"SK_X"}'},
    }, {
        "id": "alternatives_call", "type": "function",
        "function": {"name": "get_alternative_events", "arguments": '{"skill_id":"SK_X"}'},
    }])
    final_message = ChatCompletionMessage(role="assistant", content="Grounded explanation")

    def response(message):
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])

    create = AsyncMock(side_effect=[response(tool_message), response(final_message)] * 2)
    fake_client(monkeypatch, create)
    answer = build_rationale("Senior", _STEP, "en", "")
    assert answer["source"] == "llm-agentic"
    assert answer["tool_calls"] == [
        {"tool": "get_skill_history", "skill_id": "SK_X"},
        {"tool": "get_alternative_events", "skill_id": "SK_X"},
    ]
    assert create.call_count == 2
    assert build_rationale("Senior", _STEP, "en", "")["text"] == answer["text"]
    assert create.call_count == 2
    changed = {**_STEP, "skills": [{**_STEP["skills"][0], "current": 2}]}
    assert build_rationale("Senior", changed, "en", "")["source"] == "llm-agentic"
    assert create.call_count == 4


def test_page_template_does_not_call_provider_even_when_configured(monkeypatch):
    fake_client(monkeypatch, AsyncMock(side_effect=AssertionError("unexpected API request")))
    assert build_rationale("Senior", _STEP, "ru", "", use_llm=False)["source"] == "template"


def test_ai_must_check_alternatives_when_history_contains_avoidance(monkeypatch):
    from openai.types.chat import ChatCompletionMessage

    history_message = ChatCompletionMessage(role="assistant", content=None, tool_calls=[{
        "id": "history_only", "type": "function",
        "function": {"name": "get_skill_history", "arguments": '{"skill_id":"SK_X"}'},
    }])
    final_message = ChatCompletionMessage(role="assistant", content="Unchecked recommendation")
    create = AsyncMock(side_effect=[
        SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])
        for message in (history_message, final_message)
    ])
    fake_client(monkeypatch, create)
    answer = build_rationale("Senior", _STEP, "en", "")
    assert answer["source"] == "template"
    assert answer["tool_calls"] == []
    assert create.call_args_list[1].kwargs["tool_choice"] == {
        "type": "function", "function": {"name": "get_alternative_events"},
    }


def test_ai_does_not_require_alternatives_without_avoidance(monkeypatch):
    from openai.types.chat import ChatCompletionMessage

    step = {**_STEP, "skills": [{**_STEP["skills"][0],
                              "history": {"completed": 1, "declined": 0, "no_show": 0, "dropped": 0}}]}
    history_message = ChatCompletionMessage(role="assistant", content=None, tool_calls=[{
        "id": "history_only", "type": "function",
        "function": {"name": "get_skill_history", "arguments": '{"skill_id":"SK_X"}'},
    }])
    final_message = ChatCompletionMessage(role="assistant", content="History checked")
    create = AsyncMock(side_effect=[
        SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])
        for message in (history_message, final_message)
    ])
    fake_client(monkeypatch, create)
    assert build_rationale("Senior", step, "en", "")["source"] == "llm-agentic"


def test_absent_history_uses_facts_without_speculative_ai_inferences(monkeypatch):
    create = AsyncMock(side_effect=AssertionError("unexpected API request"))
    fake_client(monkeypatch, create)
    step = {**_STEP, "skills": [{**_STEP["skills"][0],
                              "history": {"completed": 0, "declined": 0, "no_show": 0, "dropped": 0}}]}
    answer = build_rationale("Senior", step, "en", "")
    assert answer["source"] == "template"
    assert answer["fallback_reason"] == "insufficient_history"
    assert "now 1" in answer["facts"]
    create.assert_not_called()
