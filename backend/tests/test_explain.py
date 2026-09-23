"""Тесты объяснения рекомендаций: шаблонный фолбэк и бюджет времени.

ТЗ: "Допустимая задержка: ... AI-рекомендация до 10 секунд" — на весь ответ, а шагов
может быть до трёх, поэтому бюджет на agentic-LLM должен быть общим, а не по шагу
(иначе 3 шага × до 8с каждый = до 24с). Проверяем, что при исчерпанном бюджете
явно не пытаемся звать LLM и мгновенно получаем шаблон, а не зависаем."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.explain import build_rationale

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
