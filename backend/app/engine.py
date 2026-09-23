"""Движок рекомендаций Career Quest.

Полностью детерминированный: ранжирует разрывы по навыкам с учётом (1) требований
следующего грейда, (2) критичности навыка для перехода (role_profiles.critical_skills),
(3) истории участия сотрудника (отказы/пропуски/завершения), затем подбирает под
каждый разрыв конкретную добровольную активность.

Почему детерминированный, а не «спросить LLM»: жюри на защите загружает три
одинаковых для всех команд проверочных профиля, специально составленных так, чтобы
однофакторное правило («бери минимальный навык») ошибалось. Взвешенная многофакторная
оценка ниже устойчива к этому по конструкции — она не может свестись к одному полю.
LLM (см. explain.py) используется только для того, чтобы облечь эти факторы в
естественный, локализованный текст — не для самого решения.
"""

from __future__ import annotations

from .store import GRADE_ORDER, DataStore

CRITICAL_WEIGHT = 2.0
NORMAL_WEIGHT = 1.0


def next_grade(role_profiles: dict, role: str, grade: str) -> str | None:
    if grade not in GRADE_ORDER:
        return None
    idx = GRADE_ORDER.index(grade)
    if idx + 1 >= len(GRADE_ORDER):
        return None
    candidate = GRADE_ORDER[idx + 1]
    return candidate if (role, candidate) in role_profiles else None


def target_for_employee(store: DataStore, emp: dict) -> tuple[str, str, dict | None]:
    """Определяет целевые role/grade для расчёта разрывов.

    Если у сотрудника задан career_goal — используем его. Иначе — следующий грейд
    в той же роли. Если сотрудник уже на верхнем грейде (Lead) без явной цели —
    считаем "поддерживающий" режим относительно требований текущего грейда
    (сравниваем с текущими требованиями, чтобы показать оставшиеся пробелы,
    а не просто говорить "рекомендаций нет").
    """
    goal = emp.get("career_goal")
    if goal:
        role, grade = goal["target_role"], goal["target_grade"]
    else:
        role = emp["role"]
        grade = next_grade(store.role_profiles, role, emp["grade"])
        if grade is None:
            role, grade = emp["role"], emp["grade"]
    profile = store.role_profiles.get((role, grade))
    return role, grade, profile


def skill_gaps(emp: dict, profile: dict | None) -> list[dict]:
    """Взвешенные разрывы по навыкам относительно целевого грейда, отсортированные
    по убыванию значимости (gap * вес критичности)."""
    if not profile:
        return []
    critical = set(profile.get("critical_skills", []))
    gaps = []
    for skill_id, required in profile["required_skills"].items():
        current = emp["skills"].get(skill_id, 0)
        gap = required - current
        if gap <= 0:
            continue
        is_critical = skill_id in critical
        weight = CRITICAL_WEIGHT if is_critical else NORMAL_WEIGHT
        gaps.append(
            {
                "skill_id": skill_id,
                "current": current,
                "required": required,
                "gap": gap,
                "critical": is_critical,
                "score": gap * weight,
            }
        )
    gaps.sort(key=lambda g: g["score"], reverse=True)
    return gaps


def history_stats_for_skill(store: DataStore, employee_id: str, skill_id: str) -> dict[str, int]:
    """Сколько раз сотрудник участвовал/пропускал/отказывался от активностей,
    развивающих конкретный навык — сигнал добровольности (см. ТЗ, «Учесть:
    принуждение — главный предиктор провала»)."""
    stats = {"completed": 0, "declined": 0, "no_show": 0, "dropped": 0, "in_progress": 0, "overdue": 0}
    for row in store.history_for_employee(employee_id):
        event = store.events.get(row["event_id"])
        if not event:
            continue
        if any(d["skill_id"] == skill_id for d in event.get("develops_skills", [])):
            status = row["status"]
            if status in stats:
                stats[status] += 1
    return stats


def candidate_events_for_skill(
    store: DataStore, emp: dict, skill_id: str, target_role: str, target_grade: str
) -> list[dict]:
    """Добровольные активности, которые: развивают нужный навык, доступны роли/грейду
    сотрудника (текущему или целевому), не были уже завершены (кроме клуба EV_036,
    он повторяемый по правилам датасета), и для которых выполнены prerequisites."""
    already_completed = store.completed_event_ids(emp["employee_id"])
    out = []
    for event_id, event in store.events.items():
        if event.get("mandatory"):
            continue
        if event_id in already_completed and event_id != "EV_036":
            continue
        if not any(d["skill_id"] == skill_id for d in event.get("develops_skills", [])):
            continue
        roles_ok = emp["role"] in event.get("target_roles", []) or target_role in event.get("target_roles", [])
        grades_ok = emp["grade"] in event.get("target_grades", []) or target_grade in event.get("target_grades", [])
        if not (roles_ok and grades_ok):
            continue
        prereqs_ok = all(
            emp["skills"].get(pre_skill, 0) >= pre_level
            for pre_skill, pre_level in event.get("prerequisites", {}).items()
        )
        if not prereqs_ok:
            continue
        out.append(event)
    return out


def recommend(store: DataStore, employee_id: str, top_n: int = 3) -> dict:
    """Главная точка входа: профиль → траектория → 1–3 рекомендованных шага
    с обоснованием, опирающимся минимум на три фактора (грейд/разрыв, критичность,
    история)."""
    emp = store.employees[employee_id]
    target_role, target_grade, profile = target_for_employee(store, emp)
    gaps = skill_gaps(emp, profile)

    avoided_events = {
        r["event_id"] for r in store.history_for_employee(employee_id) if r["status"] in ("declined", "no_show", "dropped")
    }

    chosen: dict[str, dict] = {}
    for gap in gaps:
        if len(chosen) >= top_n:
            break
        skill_id = gap["skill_id"]
        candidates = candidate_events_for_skill(store, emp, skill_id, target_role, target_grade)
        if not candidates:
            continue
        history = history_stats_for_skill(store, employee_id, skill_id)

        def sort_key(ev: dict) -> tuple:
            gain = next((d["gain"] for d in ev["develops_skills"] if d["skill_id"] == skill_id), 0)
            was_avoided = ev["event_id"] in avoided_events
            return (was_avoided, -gain)

        candidates.sort(key=sort_key)
        best = candidates[0]
        alternatives = [
            {"event_id": c["event_id"], "title": c["title"]} for c in candidates[1:3] if c["event_id"] != best["event_id"]
        ]
        entry = chosen.setdefault(best["event_id"], {"event": best, "skills": []})
        entry["skills"].append(
            {
                **gap,
                "history": history,
                "was_avoided_before": best["event_id"] in avoided_events,
                "alternative_events": alternatives,
            }
        )

    steps = list(chosen.values())[:top_n]
    return {
        "employee_id": employee_id,
        "target_role": target_role,
        "target_grade": target_grade,
        "gaps": gaps,
        "steps": steps,
        "readiness_percent": readiness_percent(profile, gaps),
    }


def readiness_percent(profile: dict | None, gaps: list[dict]) -> int:
    """Доля требований целевого грейда, уже выполненных сотрудником, 0–100.
    Простая, проверяемая метрика «насколько близко к следующему грейду» — использована
    и в интерфейсе сотрудника (прогресс-бар), и в HR-обзоре (кто дальше всех/ближе всех)."""
    if not profile or not profile.get("required_skills"):
        return 100
    total = len(profile["required_skills"])
    unmet = len(gaps)
    return round(100 * (total - unmet) / total)


def hr_overview(store: DataStore) -> dict:
    """Агрегированный срез для HR: какие навыки чаще всего проседают, у кого нет
    рекомендованного шага, участие по активностям (must-have «Простой HR-view»)."""
    skill_gap_count: dict[str, int] = {}
    skill_gap_sum: dict[str, float] = {}
    employees_without_step: list[str] = []
    readiness_by_employee: dict[str, int] = {}

    for employee_id, emp in store.employees.items():
        result = recommend(store, employee_id)
        for gap in result["gaps"]:
            skill_gap_count[gap["skill_id"]] = skill_gap_count.get(gap["skill_id"], 0) + 1
            skill_gap_sum[gap["skill_id"]] = skill_gap_sum.get(gap["skill_id"], 0) + gap["gap"]
        if not result["steps"]:
            employees_without_step.append(employee_id)
        readiness_by_employee[employee_id] = result["readiness_percent"]

    lowest_readiness = sorted(readiness_by_employee.items(), key=lambda kv: kv[1])[:10]

    top_lagging_skills = sorted(
        (
            {
                "skill_id": skill_id,
                "employees_with_gap": count,
                "avg_gap": round(skill_gap_sum[skill_id] / count, 2),
            }
            for skill_id, count in skill_gap_count.items()
        ),
        key=lambda x: x["employees_with_gap"],
        reverse=True,
    )[:15]

    participation: dict[str, dict[str, int]] = {}
    for row in store.history:
        event_id = row["event_id"]
        bucket = participation.setdefault(event_id, {"completed": 0, "declined": 0, "no_show": 0, "dropped": 0, "other": 0})
        status = row["status"]
        bucket[status if status in bucket else "other"] += 1

    return {
        "top_lagging_skills": top_lagging_skills,
        "employees_without_step": employees_without_step,
        "participation_by_event": participation,
        "total_employees": len(store.employees),
        "lowest_readiness": lowest_readiness,
    }
