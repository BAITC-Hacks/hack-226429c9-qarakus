"""Career Quest — FastAPI приложение.

Один процесс: отдаёт и API (JSON), и HTML-страницы (Jinja2 + Tailwind CDN, без
отдельной сборки фронтенда) — это осознанное решение под требование ТЗ «запуск
одной командой» и под явное указание в кейсе: «ядро задачи — качество и
объяснимость рекомендации, а не интерфейсная обвязка».
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import engine
from .store import store

import json as _json


async def _parse_upload(
    employees_file: UploadFile | None, history_file: UploadFile | None
) -> tuple[int, int]:
    """Общий разбор загрузки для /hr/upload и /api/data/upload. Валидирует формат
    заранее и поднимает HTTPException с понятным сообщением вместо падения с 500 —
    жюри может загрузить не совсем тот файл, и это не должно ронять приложение."""
    added_employees = 0
    added_history = 0

    if employees_file is not None and employees_file.filename:
        try:
            raw = _json.loads((await employees_file.read()).decode("utf-8"))
        except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Файл профилей — не валидный JSON: {exc}")
        rows = raw["employees"] if isinstance(raw, dict) and "employees" in raw else raw
        if not isinstance(rows, list) or not all(isinstance(r, dict) and "employee_id" in r for r in rows):
            raise HTTPException(
                status_code=400,
                detail="Файл профилей должен быть списком объектов employees.json с полем employee_id у каждого",
            )
        added_employees = store.add_employees(rows)

    if history_file is not None and history_file.filename:
        try:
            text = (await history_file.read()).decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(text)))
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Файл истории — не валидный CSV: {exc}")
        required_columns = {"employee_id", "event_id", "status"}
        if rows and not required_columns.issubset(rows[0].keys()):
            raise HTTPException(
                status_code=400,
                detail=f"В CSV должны быть колонки {sorted(required_columns)} (как в activity_history.csv)",
            )
        added_history = store.add_history(rows)

    return added_employees, added_history

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
    return templates.TemplateResponse("index.html", {"request": request, "error": None})


@app.get("/login")
def login(request: Request, employee_id: str):
    employee_id = employee_id.strip().upper()
    if employee_id not in store.employees:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": f"Сотрудник «{employee_id}» не найден. Проверьте ID."},
            status_code=404,
        )
    return RedirectResponse(url=f"/employee/{employee_id}", status_code=303)


@app.get("/employee/{employee_id}")
def employee_page(request: Request, employee_id: str):
    emp = store.employees.get(employee_id)
    if emp is None:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": f"Сотрудник «{employee_id}» не найден. Проверьте ID."},
            status_code=404,
        )

    result = engine.recommend(store, employee_id)
    history = sorted(store.history_for_employee(employee_id), key=lambda r: r["date"], reverse=True)

    steps_view = []
    for step in result["steps"]:
        rationale = _rationale_for(emp, result["target_grade"], step)
        steps_view.append(
            {
                "event": step["event"],
                "skills": [{**s, "skill_name": _skill_name(s["skill_id"])} for s in step["skills"]],
                "rationale": rationale,
            }
        )

    return templates.TemplateResponse(
        "employee.html",
        {
            "request": request,
            "emp": emp,
            "target_role": result["target_role"],
            "target_grade": result["target_grade"],
            "gaps": [{**g, "skill_name": _skill_name(g["skill_id"])} for g in result["gaps"]],
            "steps": steps_view,
            "history": history,
            "skill_name": _skill_name,
            "events": store.events,
            "readiness_percent": result["readiness_percent"],
        },
    )


def _rationale_for(emp: dict, target_grade: str, step: dict) -> dict:
    from .explain import build_rationale

    return build_rationale(target_grade, step, emp.get("preferred_language", "ru"), emp.get("full_name", emp["employee_id"]))


@app.post("/employee/{employee_id}/complete/{event_id}")
def complete_activity(employee_id: str, event_id: str):
    if employee_id not in store.employees or event_id not in store.events:
        raise HTTPException(status_code=404, detail="Сотрудник или активность не найдены")
    store.complete_activity(employee_id, event_id)
    return RedirectResponse(url=f"/employee/{employee_id}", status_code=303)


# ---------------------------------------------------------------------------
# HTML: HR
# ---------------------------------------------------------------------------


@app.get("/hr")
def hr_page(request: Request, uploaded: int | None = None):
    overview = engine.hr_overview(store)
    lagging = [{**s, "skill_name": _skill_name(s["skill_id"])} for s in overview["top_lagging_skills"]]
    without_step = [store.employees[eid] for eid in overview["employees_without_step"] if eid in store.employees]
    lowest_readiness = [
        {**store.employees[eid], "readiness_percent": pct}
        for eid, pct in overview["lowest_readiness"]
        if eid in store.employees
    ]
    return templates.TemplateResponse(
        "hr.html",
        {
            "request": request,
            "lagging": lagging,
            "without_step": without_step,
            "lowest_readiness": lowest_readiness,
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


@app.get("/api/employees")
def api_employees():
    return [
        {"employee_id": e["employee_id"], "full_name": e["full_name"], "role": e["role"], "grade": e["grade"]}
        for e in sorted(store.employees.values(), key=lambda e: e["employee_id"])
    ]


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
        raise HTTPException(status_code=404, detail="not found")
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
