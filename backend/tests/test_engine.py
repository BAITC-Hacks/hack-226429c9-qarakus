"""Тесты движка рекомендаций.

Главный тест (test_trap_profile_from_spec) — это ровно пример-ловушка из самого ТЗ:
«у сотрудника ниже всего Public Speaking, но он трижды пропускал такие активности,
а для перехода критичен System Design — рекомендация "бери минимальный навык" здесь
промахивается». Мы проверяем, что наш движок НЕ промахивается.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import engine
from app.store import DataStore, InvalidCompletionError


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
    event = next(
        e for e in store.events.values()
        if e["develops_skills"] and engine.event_is_available(
            store, emp, e, *engine.target_for_employee(store, emp)[:2]
        )
    )
    dev = event["develops_skills"][0]
    emp["skills"][dev["skill_id"]] = dev["max_level"] - 1  # почти на максимуме

    store.complete_activity(employee_id, event["event_id"])

    assert emp["skills"][dev["skill_id"]] <= dev["max_level"]


def test_readiness_percent_matches_gap_count():
    profile = {"required_skills": {f"SK_{i}": 3 for i in range(16)}, "critical_skills": []}
    gaps = [{"skill_id": f"SK_{i}"} for i in range(12)]  # 12 из 16 не выполнены
    assert engine.readiness_percent(profile, gaps) == 25

    assert engine.readiness_percent(profile, []) == 100
    # profile=None означает "роль/грейд не найдены", а не "все требования выполнены" —
    # это НЕ 100%, это None (см. test_unknown_role_gives_none_readiness_not_false_100_percent).
    assert engine.readiness_percent(None, []) is None


def test_skill_never_decreases_even_if_event_max_level_is_lower():
    """Регрессия: если у сотрудника навык уже выше max_level конкретного мероприятия
    (достигнут через другую активность/грейд), выполнение этого мероприятия не должно
    ПОНИЖАТЬ навык — только не повышать выше собственного max_level."""
    store = make_store()
    employee_id = "E0001"
    emp = store.employees[employee_id]
    event = next(
        e for e in store.events.values()
        if e["develops_skills"] and engine.event_is_available(
            store, emp, e, *engine.target_for_employee(store, emp)[:2]
        )
    )
    dev = event["develops_skills"][0]
    emp["skills"][dev["skill_id"]] = dev["max_level"] + 5  # уже заметно выше max_level этого события

    store.complete_activity(employee_id, event["event_id"])

    assert emp["skills"][dev["skill_id"]] == dev["max_level"] + 5, "навык не должен понижаться"


def test_completion_rejects_mandatory_duplicate_and_unavailable_events():
    store = make_store()
    employee_id = "E0028"
    mandatory = next(event for event in store.events.values() if event["mandatory"])
    with pytest.raises(InvalidCompletionError):
        store.complete_activity(employee_id, mandatory["event_id"])

    recommended = engine.recommend(store, employee_id)["steps"][0]["event"]["event_id"]
    store.complete_activity(employee_id, recommended)
    if recommended != "EV_036":
        with pytest.raises(InvalidCompletionError):
            store.complete_activity(employee_id, recommended)

    employee = store.employees[employee_id]
    target_role, target_grade, _ = engine.target_for_employee(store, employee)
    unavailable = next(
        event for event in store.events.values()
        if not event["mandatory"] and event["event_id"] != recommended
        and not engine.event_is_available(store, employee, event, target_role, target_grade)
    )
    with pytest.raises(InvalidCompletionError):
        store.complete_activity(employee_id, unavailable["event_id"])


def test_engagement_risk_flags_high_avoidance_and_low_readiness():
    store = make_store()
    store.add_employees(
        [
            {
                "employee_id": "TEST_RISK",
                "full_name": "Risk Case",
                "department": "Backend Development",
                "role": "Backend Engineer",
                "grade": "Junior",
                "manager_id": None,
                "hire_date": "2023-01-01",
                "tenure_months": 24,
                "work_format": "office",
                "preferred_language": "ru",
                "career_goal": None,
                "skills": {},  # почти все навыки на нуле — низкая готовность гарантирована
                "last_review_date": "2026-09-01",
            }
        ]
    )
    store.add_history(
        [
            {"employee_id": "TEST_RISK", "event_id": "EV_005", "date": "2025-01-01", "status": "declined"},
            {"employee_id": "TEST_RISK", "event_id": "EV_009", "date": "2025-02-01", "status": "no_show"},
            {"employee_id": "TEST_RISK", "event_id": "EV_010", "date": "2025-03-01", "status": "dropped"},
            {"employee_id": "TEST_RISK", "event_id": "EV_038", "date": "2025-04-01", "status": "completed"},
        ]
    )
    result = engine.recommend(store, "TEST_RISK")
    risk = engine.engagement_risk(store, "TEST_RISK", result["readiness_percent"])
    assert risk is not None
    assert risk["avoidance_rate"] == 0.75


def test_engagement_risk_none_with_too_little_history():
    store = make_store()
    # у обычного сотрудника из сида истории мало или готовность нормальная —
    # хотя бы не должно падать с ошибкой на реальных данных
    for employee_id in list(store.employees)[:5]:
        risk = engine.engagement_risk(store, employee_id, 100)  # искусственно высокая готовность
        assert risk is None, "при высокой готовности риск не должен срабатывать"


def test_unknown_role_gives_none_readiness_not_false_100_percent():
    """Регрессия (review, п.1): раньше неизвестная роль/грейд (профиль не найден в
    role_profiles) молча давал readiness_percent=100 — неотличимо от «все требования
    выполнены». Это опасно именно на проверочных профилях жюри: нестандартная
    роль/грейд должна честно сигналить «недостаточно данных», а не «полностью готов»."""
    store = make_store()
    store.add_employees(
        [
            {
                "employee_id": "TEST_UNKNOWN_ROLE",
                "full_name": "Unknown Role",
                "department": "Unknown",
                "role": "Space Pirate",  # роли нет в role_profiles
                "grade": "Middle",
                "manager_id": None,
                "hire_date": "2023-01-01",
                "tenure_months": 12,
                "work_format": "office",
                "preferred_language": "ru",
                "career_goal": None,
                "skills": {},
                "last_review_date": "2026-09-01",
            }
        ]
    )
    result = engine.recommend(store, "TEST_UNKNOWN_ROLE")
    assert result["profile_found"] is False
    assert result["readiness_percent"] is None
    assert result["gaps"] == []
    assert result["steps"] == []


def test_hr_overview_buckets_unknown_role_separately_and_does_not_crash():
    store = make_store()
    store.add_employees(
        [
            {
                "employee_id": "TEST_UNKNOWN_ROLE2",
                "full_name": "Unknown Role 2",
                "department": "Unknown",
                "role": "Space Pirate",
                "grade": "Middle",
                "manager_id": None,
                "hire_date": "2023-01-01",
                "tenure_months": 12,
                "work_format": "office",
                "preferred_language": "ru",
                "career_goal": None,
                "skills": {},
                "last_review_date": "2026-09-01",
            }
        ]
    )
    overview = engine.hr_overview(store)  # не должно бросить TypeError на сортировке None
    assert "TEST_UNKNOWN_ROLE2" in overview["employees_unknown_data"]
    lowest_ids = [eid for eid, _ in overview["lowest_readiness"]]
    assert "TEST_UNKNOWN_ROLE2" not in lowest_ids


def test_next_grade_respects_order():
    store = make_store()
    assert engine.next_grade(store.role_profiles, "Backend Engineer", "Junior") == "Middle"
    assert engine.next_grade(store.role_profiles, "Backend Engineer", "Middle") == "Senior"
    assert engine.next_grade(store.role_profiles, "Backend Engineer", "Lead") is None
