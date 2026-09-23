"""Тесты движка рекомендаций.

Главный тест (test_trap_profile_from_spec) — это ровно пример-ловушка из самого ТЗ:
«у сотрудника ниже всего Public Speaking, но он трижды пропускал такие активности,
а для перехода критичен System Design — рекомендация "бери минимальный навык" здесь
промахивается». Мы проверяем, что наш движок НЕ промахивается.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import engine
from app.store import DataStore


def make_store() -> DataStore:
    # Переиспользуем загрузку сида, но с чистой историей на каждый тест,
    # чтобы тесты не зависели друг от друга.
    return DataStore()


def test_trap_profile_from_spec():
    """Ровно пример из ТЗ: критичный навык должен обгонять численно самый низкий,
    даже когда по низкому навыку есть история пропусков."""
    store = make_store()
    store.add_employees(
        [
            {
                "employee_id": "TEST_TRAP",
                "full_name": "Test Trap",
                "department": "Backend Development",
                "role": "Backend Engineer",
                "grade": "Middle",
                "manager_id": None,
                "hire_date": "2023-01-01",
                "tenure_months": 36,
                "work_format": "office",
                "preferred_language": "ru",
                "career_goal": None,
                "skills": {
                    "SK_PYTHON": 3,
                    "SK_SQL": 3,
                    "SK_API_DESIGN": 3,
                    "SK_SYSTEM_DESIGN": 2,  # разрыв 2 до Senior (требуется 4), КРИТИЧНО
                    "SK_CLOUD": 3,
                    "SK_CONTAINERS": 3,
                    "SK_CICD": 3,
                    "SK_APP_SECURITY": 3,
                    "SK_OBSERVABILITY": 3,
                    "SK_COMMUNICATION": 3,
                    "SK_TEAMWORK": 3,
                    "SK_PROBLEM_SOLVING": 3,
                    "SK_MENTORING": 2,
                    "SK_STAKEHOLDER_MGMT": 2,
                    "SK_PUBLIC_SPEAKING": 0,  # самый низкий в абсолютных числах, но НЕ критичен
                },
                "last_review_date": "2026-09-01",
            }
        ]
    )
    store.add_history(
        [
            {"employee_id": "TEST_TRAP", "event_id": "EV_036", "date": "2025-01-10", "status": "declined"},
            {"employee_id": "TEST_TRAP", "event_id": "EV_036", "date": "2025-04-10", "status": "no_show"},
            {"employee_id": "TEST_TRAP", "event_id": "EV_036", "date": "2025-08-10", "status": "declined"},
        ]
    )

    result = engine.recommend(store, "TEST_TRAP")

    assert result["gaps"], "должны быть найдены разрывы"
    top_gap = result["gaps"][0]
    assert top_gap["skill_id"] == "SK_SYSTEM_DESIGN", (
        f"ловушка не пройдена: движок поставил первым {top_gap['skill_id']}, "
        f"а должен был System Design (критичный навык), а не Public Speaking "
        f"(численно ниже, но не критичен)"
    )
    assert top_gap["critical"] is True

    # Public Speaking Club (EV_036) сотрудник уже трижды пропускал/отклонял —
    # если он всё же попал в рекомендации, это должно быть явно помечено.
    for step in result["steps"]:
        if step["event"]["event_id"] == "EV_036":
            assert step["skills"][0]["was_avoided_before"] is True


def test_critical_skill_outweighs_larger_noncritical_gap():
    """Критичный навык с меньшим разрывом должен побеждать некритичный навык
    с большим разрывом, если взвешенный score выше (gap=1 критичный = score 2,
    gap=2 некритичный = score 2 — граничный случай; здесь берём gap=2 критичный
    (score 4) против gap=3 некритичного (score 3))."""
    store = make_store()
    profile = store.role_profiles[("Backend Engineer", "Middle")]
    emp = dict(store.employees["E0001"])
    emp["employee_id"] = "TEST_WEIGHT"
    emp["skills"] = dict(emp["skills"])
    for skill_id, level in profile["required_skills"].items():
        emp["skills"][skill_id] = level  # закрываем все разрывы
    critical_skill = profile["critical_skills"][0]
    other_skill = next(s for s in profile["required_skills"] if s not in profile["critical_skills"])
    emp["skills"][critical_skill] = profile["required_skills"][critical_skill] - 2
    emp["skills"][other_skill] = profile["required_skills"][other_skill] - 3
    store.add_employees([emp])

    gaps = engine.skill_gaps(emp, profile)
    scores = {g["skill_id"]: g["score"] for g in gaps}
    assert scores[critical_skill] == 4.0
    assert scores[other_skill] == 3.0
    assert gaps[0]["skill_id"] == critical_skill


def test_mandatory_events_never_recommended():
    store = make_store()
    for step in engine.recommend(store, "E0001")["steps"]:
        assert step["event"]["mandatory"] is False


def test_completed_event_not_recommended_again():
    store = make_store()
    employee_id = "E0028"
    before = engine.recommend(store, employee_id)
    assert before["steps"], "нужен хотя бы один шаг для проверки"
    target_event = before["steps"][0]["event"]["event_id"]

    store.complete_activity(employee_id, target_event)
    after = engine.recommend(store, employee_id)
    after_event_ids = {s["event"]["event_id"] for s in after["steps"]}
    assert target_event not in after_event_ids or target_event == "EV_036"


def test_skill_gain_capped_at_max_level():
    store = make_store()
    employee_id = "E0001"
    emp = store.employees[employee_id]
    event = next(e for e in store.events.values() if e["develops_skills"] and not e["mandatory"])
    dev = event["develops_skills"][0]
    emp["skills"][dev["skill_id"]] = dev["max_level"] - 1  # почти на максимуме

    store.complete_activity(employee_id, event["event_id"])

    assert emp["skills"][dev["skill_id"]] <= dev["max_level"]


def test_readiness_percent_matches_gap_count():
    profile = {"required_skills": {f"SK_{i}": 3 for i in range(16)}, "critical_skills": []}
    gaps = [{"skill_id": f"SK_{i}"} for i in range(12)]  # 12 из 16 не выполнены
    assert engine.readiness_percent(profile, gaps) == 25

    assert engine.readiness_percent(profile, []) == 100
    assert engine.readiness_percent(None, []) == 100


def test_skill_never_decreases_even_if_event_max_level_is_lower():
    """Регрессия: если у сотрудника навык уже выше max_level конкретного мероприятия
    (достигнут через другую активность/грейд), выполнение этого мероприятия не должно
    ПОНИЖАТЬ навык — только не повышать выше собственного max_level."""
    store = make_store()
    employee_id = "E0001"
    emp = store.employees[employee_id]
    event = next(e for e in store.events.values() if e["develops_skills"] and not e["mandatory"])
    dev = event["develops_skills"][0]
    emp["skills"][dev["skill_id"]] = dev["max_level"] + 5  # уже заметно выше max_level этого события

    store.complete_activity(employee_id, event["event_id"])

    assert emp["skills"][dev["skill_id"]] == dev["max_level"] + 5, "навык не должен понижаться"


def test_next_grade_respects_order():
    store = make_store()
    assert engine.next_grade(store.role_profiles, "Backend Engineer", "Junior") == "Middle"
    assert engine.next_grade(store.role_profiles, "Backend Engineer", "Middle") == "Senior"
    assert engine.next_grade(store.role_profiles, "Backend Engineer", "Lead") is None
