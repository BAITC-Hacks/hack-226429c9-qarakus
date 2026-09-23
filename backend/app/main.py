"""Career Quest — FastAPI приложение.

Один процесс: отдаёт и API (JSON), и HTML-страницы (Jinja2 + Tailwind CDN, без
отдельной сборки фронтенда) — это осознанное решение под требование ТЗ «запуск
одной командой» и под явное указание в кейсе: «ядро задачи — качество и
объяснимость рекомендации, а не интерфейсная обвязка».
"""

from __future__ import annotations

import csv
import datetime
import io
import json as _json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import engine
from .i18n import resolve_lang, translate
from .store import InvalidCompletionError, store


def _lang_for_request(request: Request, *extra_candidates: str | None) -> str:
    """Приоритет: явный ?lang= в URL > доп. кандидаты (например, preferred_language
    сотрудника) > сохранённый cookie > русский по умолчанию."""
    return resolve_lang(request.query_params.get("lang"), *extra_candidates, request.cookies.get("lang"))


def _render(request: Request, template_name: str, lang: str, context: dict, status_code: int = 200):
    ctx = {"request": request, "lang": lang, "t": lambda key, **fmt: translate(lang, key, **fmt), **context}
    response = templates.TemplateResponse(template_name, ctx, status_code=status_code)
    if request.query_params.get("lang"):
        response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 30)
    return response


async def _parse_upload(
    employees_file: UploadFile | None, history_file: UploadFile | None
) -> tuple[int, int]:
    """Общий разбор загрузки для /hr/upload и /api/data/upload. Валидирует формат
    заранее и поднимает HTTPException с понятным сообщением вместо падения с 500 —
    жюри может загрузить не совсем тот файл, и это не должно ронять приложение."""
    employees = []
    history = []

    if employees_file is not None and employees_file.filename:
        try:
            raw = _json.loads((await employees_file.read()).decode("utf-8"))
        except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Файл профилей — не валидный JSON: {exc}") from exc
        employees = raw["employees"] if isinstance(raw, dict) and "employees" in raw else raw
        if not isinstance(employees, list):
            raise HTTPException(
                status_code=400,
                detail="Файл профилей должен содержать список employees.json",
            )
        required_employee_fields = {"employee_id", "full_name", "role", "grade", "skills"}
        for index, employee in enumerate(employees, 1):
            if not isinstance(employee, dict) or not required_employee_fields.issubset(employee):
                raise HTTPException(
                    status_code=400, detail=f"Профиль {index}: нужны поля {sorted(required_employee_fields)}"
                )
            text_fields = required_employee_fields - {"skills"}
            if not all(isinstance(employee[field], str) and employee[field] for field in text_fields):
                raise HTTPException(
                    status_code=400, detail=f"Профиль {index}: ID, имя, роль и грейд должны быть строками"
                )
            skills = employee["skills"]
            if not isinstance(skills, dict) or any(
                skill_id not in store.skills_catalog or type(level) is not int or not 0 <= level <= 5
                for skill_id, level in skills.items()
            ):
                raise HTTPException(
                    status_code=400, detail=f"Профиль {index}: навыки должны содержать известные ID и уровни 0–5"
                )
            goal = employee.get("career_goal")
            if goal is not None and (
                not isinstance(goal, dict)
                or not all(isinstance(goal.get(field), str) for field in ("target_role", "target_grade"))
            ):
                raise HTTPException(status_code=400, detail=f"Профиль {index}: неверный career_goal")

    if history_file is not None and history_file.filename:
        try:
            text = (await history_file.read()).decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            required_columns = {"employee_id", "event_id", "date", "status"}
            if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
                raise HTTPException(
                    status_code=400,
                    detail=f"В CSV должны быть колонки {sorted(required_columns)} (как в activity_history.csv)",
                )
            history = list(reader)
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Файл истории — не валидный CSV: {exc}") from exc
        known_employees = store.employees.keys() | {employee["employee_id"] for employee in employees}
        valid_statuses = {"completed", "declined", "no_show", "dropped", "in_progress", "overdue"}
        for index, row in enumerate(history, 2):
            try:
                datetime.date.fromisoformat(row["date"])
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Строка CSV {index}: неверная дата") from None
            if row["employee_id"] not in known_employees or row["event_id"] not in store.events:
                raise HTTPException(
                    status_code=400, detail=f"Строка CSV {index}: неизвестный сотрудник или мероприятие"
                )
            if row["status"] not in valid_statuses:
                raise HTTPException(status_code=400, detail=f"Строка CSV {index}: неизвестный статус")

    return store.import_data(employees, history)

app = FastAPI(title="Career Quest", description="AI-навигатор развития сотрудника (HackAlem AI, трек Halyk Bank)")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _skill_name(skill_id: str) -> str:
    s = store.skills_catalog.get(skill_id)
    return s["name"] if s else skill_id


# ---------------------------------------------------------------------------
# HTML: сотрудник
# ---------------------------------------------------------------------------


@app.get("/")
def index(request: Request):
    lang = _lang_for_request(request)
    return _render(request, "index.html", lang, {"error": None})


@app.get("/login")
def login(request: Request, employee_id: str):
    employee_id = employee_id.strip().upper()
    lang = _lang_for_request(request)
    if employee_id not in store.employees:
        error = {"error": translate(lang, "not_found", id=employee_id)}
        return _render(request, "index.html", lang, error, status_code=404)
    return RedirectResponse(url=f"/employee/{employee_id}", status_code=303)


@app.get("/employee/{employee_id}")
def employee_page(request: Request, employee_id: str):
    emp = store.employees.get(employee_id)
    if emp is None:
        lang = _lang_for_request(request)
        error = {"error": translate(lang, "not_found", id=employee_id)}
        return _render(request, "index.html", lang, error, status_code=404)

    lang = _lang_for_request(request, emp.get("preferred_language"))
    result = engine.recommend(store, employee_id)
    history = sorted(store.history_for_employee(employee_id), key=lambda r: r["date"], reverse=True)

    changed_raw = request.query_params.get("changed", "")
    changed = []
    for part in changed_raw.split(","):
        if not part:
            continue
        sid, before_v, after_v = part.split(":")
        changed.append({"skill_name": _skill_name(sid), "before": int(before_v), "after": int(after_v)})

    # Общий дедлайн на ВСЕ шаги этой страницы: ТЗ ограничивает AI-рекомендацию
    # 10 секундами целиком, а шагов может быть до трёх (см. explain.py).
    import time as _time

    deadline = _time.monotonic() + 8.0

    steps_view = []
    for step in result["steps"]:
        named_step = {
            **step,
            "skills": [{**skill, "skill_name": _skill_name(skill["skill_id"])} for skill in step["skills"]],
        }
        rationale = _rationale_for(emp, result["target_grade"], named_step, deadline)
        steps_view.append(
            {
                "event": step["event"],
                "skills": named_step["skills"],
                "rationale": rationale,
            }
        )

    return _render(
        request,
        "employee.html",
        lang,
        {
            "emp": emp,
            "target_role": result["target_role"],
            "target_grade": result["target_grade"],
            "gaps": [{**g, "skill_name": _skill_name(g["skill_id"])} for g in result["gaps"]],
            "steps": steps_view,
            "history": history,
            "skill_name": _skill_name,
            "events": store.events,
            "readiness_percent": result["readiness_percent"],
            "changed": changed,
        },
    )


def _rationale_for(emp: dict, target_grade: str, step: dict, deadline: float | None = None) -> dict:
    from .explain import build_rationale

    lang = emp.get("preferred_language", "ru")
    name = emp.get("full_name", emp["employee_id"])
    return build_rationale(target_grade, step, lang, name, deadline=deadline)


@app.post("/employee/{employee_id}/complete/{event_id}")
def complete_activity(employee_id: str, event_id: str):
    if employee_id not in store.employees or event_id not in store.events:
        raise HTTPException(status_code=404, detail="Сотрудник или активность не найдены")

    # Explainability (ТЗ): «видно... как рассчитано продвижение» — снимаем срез навыков
    # ДО применения gain, чтобы после показать явное «было → стало», а не просто новые
    # цифры без объяснения, что именно изменилось.
    event = store.events[event_id]
    current_skills = store.employees[employee_id]["skills"]
    before = {d["skill_id"]: current_skills.get(d["skill_id"], 0) for d in event.get("develops_skills", [])}
    try:
        store.complete_activity(employee_id, event_id)
    except InvalidCompletionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    after = {sid: store.employees[employee_id]["skills"].get(sid, 0) for sid in before}
    changed = ",".join(f"{sid}:{before[sid]}:{after[sid]}" for sid in before if after[sid] != before[sid])

    url = f"/employee/{employee_id}"
    if changed:
        url += f"?changed={changed}"
    return RedirectResponse(url=url, status_code=303)


# ---------------------------------------------------------------------------
# HTML: HR
# ---------------------------------------------------------------------------


@app.get("/hr")
def hr_page(request: Request, uploaded: int | None = None):
    lang = _lang_for_request(request)
    overview = engine.hr_overview(store)
    lagging = [{**s, "skill_name": _skill_name(s["skill_id"])} for s in overview["top_lagging_skills"]]
    without_step = [store.employees[eid] for eid in overview["employees_without_step"] if eid in store.employees]
    lowest_readiness = [
        {**store.employees[eid], "readiness_percent": pct}
        for eid, pct in overview["lowest_readiness"]
        if eid in store.employees
    ]
    engagement_risk = [
        {**store.employees[r["employee_id"]], **r}
        for r in overview["engagement_risk"]
        if r["employee_id"] in store.employees
    ]
    unknown_data = [store.employees[eid] for eid in overview["employees_unknown_data"] if eid in store.employees]
    return _render(
        request,
        "hr.html",
        lang,
        {
            "lagging": lagging,
            "without_step": without_step,
            "lowest_readiness": lowest_readiness,
            "engagement_risk": engagement_risk,
            "unknown_data": unknown_data,
            "participation": overview["participation_by_event"],
            "events": store.events,
            "total_employees": overview["total_employees"],
            "uploaded": uploaded,
        },
    )


@app.post("/hr/upload")
async def hr_upload(
    employees_file: UploadFile | None = File(default=None),
    history_file: UploadFile | None = File(default=None),
):
    """HTML-обёртка над /api/data/upload — форма на странице HR для проверочных
    профилей жюри (см. README, «Как проверить решение»)."""
    added_e, added_h = await _parse_upload(employees_file, history_file)
    return RedirectResponse(url=f"/hr?uploaded={added_e + added_h}", status_code=303)


# ---------------------------------------------------------------------------
# JSON API — для проверки жюри и программного доступа
# ---------------------------------------------------------------------------


@app.get("/api/employees/{employee_id}")
def api_employee(employee_id: str):
    if employee_id not in store.employees:
        raise HTTPException(status_code=404, detail="not found")
    return engine.recommend(store, employee_id)


@app.post("/api/employees/{employee_id}/complete/{event_id}")
def api_complete(employee_id: str, event_id: str):
    try:
        record = store.complete_activity(employee_id, event_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found") from None
    except InvalidCompletionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"record": record, "profile": engine.recommend(store, employee_id)}


@app.get("/api/hr/overview")
def api_hr_overview():
    return engine.hr_overview(store)


@app.post("/api/data/upload")
async def api_upload(
    employees_file: UploadFile | None = File(default=None),
    history_file: UploadFile | None = File(default=None),
):
    """Загрузка дополнительных профилей/истории в формате датасета — для проверочных
    профилей жюри (ТЗ, п.7: «на защите жюри загружает проверочные профили»).
    Принимает employees.json-подобный JSON (объект {"employees": [...]} или просто
    список) и/или activity_history.csv-подобный CSV с теми же колонками."""
    added_employees, added_history = await _parse_upload(employees_file, history_file)
    return {"added_employees": added_employees, "added_history_records": added_history}


@app.get("/health")
def health():
    return {"status": "ok", "employees": len(store.employees), "events": len(store.events)}
