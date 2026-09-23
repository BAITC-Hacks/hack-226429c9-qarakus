"""Career Quest — FastAPI приложение.

Один процесс: отдаёт и API (JSON), и HTML-страницы (Jinja2 + готовый CSS, без
отдельной сборки фронтенда) — это осознанное решение под требование ТЗ «запуск
одной командой» и под явное указание в кейсе: «ядро задачи — качество и
объяснимость рекомендации, а не интерфейсная обвязка».
"""

from __future__ import annotations

import csv
import datetime
import io
import json as _json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import engine
from .auth import authenticate, demo_mode, require_csrf, require_employee, require_hr
from .i18n import resolve_lang, translate
from .store import InvalidCompletionError, store


def _lang_for_request(request: Request, *extra_candidates: str | None) -> str:
    """Приоритет: явный ?lang= в URL > доп. кандидаты (например, preferred_language
    сотрудника) > сохранённый cookie > русский по умолчанию."""
    return resolve_lang(request.query_params.get("lang"), *extra_candidates, request.cookies.get("lang"))


def _render(request: Request, template_name: str, lang: str, context: dict, status_code: int = 200):
    csrf_token = request.session.setdefault("csrf_token", secrets.token_urlsafe(24))
    ctx = {"request": request, "lang": lang, "t": lambda key, **fmt: translate(lang, key, **fmt),
           "as_of_date": store.as_of_date, "csrf_token": csrf_token, "demo_mode": demo_mode(),
           "user_role": request.session.get("role"), **context}
    response = templates.TemplateResponse(request=request, name=template_name, context=ctx, status_code=status_code)
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

    async def read_file(upload: UploadFile) -> str:
        content = await upload.read(5 * 1024 * 1024 + 1)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Максимальный размер файла — 5 МБ")
        return content.decode("utf-8-sig")

    if employees_file is not None and employees_file.filename:
        try:
            raw = _json.loads(await read_file(employees_file))
        except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Файл профилей — не валидный JSON: {exc}") from exc
        employees = raw["employees"] if isinstance(raw, dict) and "employees" in raw else raw
        if not isinstance(employees, list):
            raise HTTPException(
                status_code=400,
                detail="Файл профилей должен содержать список employees.json",
            )
        required_employee_fields = {"employee_id", "full_name", "role", "grade", "skills"}
        employee_ids = set()
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
            employee_id = employee["employee_id"]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", employee_id) or employee_id in employee_ids:
                raise HTTPException(status_code=400, detail=f"Профиль {index}: неверный или повторяющийся ID")
            employee_ids.add(employee_id)
            if employee.get("preferred_language", "ru") not in ("ru", "kk", "en"):
                raise HTTPException(status_code=400, detail=f"Профиль {index}: язык должен быть ru, kk или en")
            reviewed = employee.get("last_review_date")
            if reviewed is not None:
                try:
                    if datetime.date.fromisoformat(reviewed).isoformat() != reviewed:
                        raise ValueError
                except (TypeError, ValueError):
                    raise HTTPException(status_code=400, detail=f"Профиль {index}: неверная дата оценки") from None
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
                or not all(isinstance(goal.get(field), str) and goal[field].strip()
                           for field in ("target_role", "target_grade"))
            ):
                raise HTTPException(status_code=400, detail=f"Профиль {index}: неверный career_goal")

    if history_file is not None and history_file.filename:
        try:
            text = await read_file(history_file)
            reader = csv.DictReader(io.StringIO(text))
            required_columns = {"employee_id", "event_id", "date", "status"}
            if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
                raise HTTPException(
                    status_code=400,
                    detail=f"В CSV должны быть колонки {sorted(required_columns)} (как в activity_history.csv)",
                )
            history = list(reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise HTTPException(status_code=400, detail=f"Файл истории — не валидный CSV: {exc}") from exc
        known_employees = store.employees.keys() | {employee["employee_id"] for employee in employees}
        valid_statuses = {"completed", "declined", "no_show", "dropped", "in_progress", "overdue"}
        for index, row in enumerate(history, 2):
            try:
                if datetime.date.fromisoformat(row["date"]).isoformat() != row["date"]:
                    raise ValueError
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Строка CSV {index}: неверная дата") from None
            if row["employee_id"] not in known_employees or row["event_id"] not in store.events:
                raise HTTPException(
                    status_code=400, detail=f"Строка CSV {index}: неизвестный сотрудник или мероприятие"
                )
            if row["status"] not in valid_statuses:
                raise HTTPException(status_code=400, detail=f"Строка CSV {index}: неизвестный статус")

    if not employees and not history:
        raise HTTPException(status_code=400, detail="Выберите непустой файл профилей или истории")
    return store.import_data(employees, history)

app = FastAPI(title="Career Quest", description="AI-навигатор развития сотрудника (HackAlem AI, трек Halyk Bank)")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32),
    max_age=8 * 60 * 60,
    same_site="strict",
    https_only=os.environ.get("SECURE_COOKIES", "false").lower() == "true",
)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, error: StarletteHTTPException):
    if request.url.path.startswith("/api/") or request.url.path == "/health":
        from fastapi.exception_handlers import http_exception_handler

        return await http_exception_handler(request, error)
    if error.status_code == 401:
        return RedirectResponse(url="/", status_code=303)
    return _render(request, "error.html", _lang_for_request(request),
                   {"detail": error.detail}, status_code=error.status_code)


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


@app.post("/login", dependencies=[Depends(require_csrf)])
def login(request: Request, employee_id: str = Form(...), password: str = Form(...)):
    employee_id = employee_id.strip()
    if employee_id != "hr" and employee_id not in store.employees:
        employee_id = employee_id.upper()
    lang = _lang_for_request(request)
    identity = authenticate(employee_id, password)
    if identity is None or (identity["role"] == "employee" and employee_id not in store.employees):
        return _render(request, "index.html", lang, {"error": translate(lang, "login_failed")}, status_code=401)
    request.session.clear()
    request.session.update(identity, csrf_token=secrets.token_urlsafe(24))
    target = "/hr" if identity["role"] == "hr" else f"/employee/{employee_id}"
    return RedirectResponse(url=f"{target}?{urlencode({'lang': lang})}", status_code=303)


@app.post("/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/session")
def api_session(request: Request):
    csrf_token = request.session.setdefault("csrf_token", secrets.token_urlsafe(24))
    return {"role": request.session.get("role"), "employee_id": request.session.get("employee_id"),
            "csrf_token": csrf_token}


@app.get("/employee/{employee_id}")
def employee_page(request: Request, employee_id: str):
    require_employee(request, employee_id)
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
        try:
            sid, before_v, after_v = part.split(":")
            before, after = int(before_v), int(after_v)
        except ValueError:
            continue
        if sid in store.skills_catalog and 0 <= before < after <= 5:
            changed.append({"skill_name": _skill_name(sid), "before": before, "after": after})

    steps_view = []
    today = store.as_of_date
    for step in result["steps"]:
        named_step = {
            **step,
            "skills": [{**skill, "skill_name": _skill_name(skill["skill_id"])} for skill in step["skills"]],
        }
        from .explain import template_rationale

        rationale = template_rationale(result["target_grade"], named_step, lang)
        sessions = sorted(date for date in step["event"].get("upcoming_sessions", []) if date >= today)
        steps_view.append(
            {
                "event": step["event"],
                "skills": named_step["skills"],
                "rationale": rationale,
                "sessions": sessions,
                "next_session": sessions[0] if sessions else None,
                "projected_readiness_percent": step["projected_readiness_percent"],
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
            "ai_enabled": bool(os.environ.get("OPENAI_API_KEY")),
            "all_skills": [
                {"name": _skill_name(skill_id), "level": level}
                for skill_id, level in sorted(emp["skills"].items(), key=lambda item: _skill_name(item[0]))
            ],
        },
    )


@app.post("/employee/{employee_id}/complete/{event_id}", dependencies=[Depends(require_csrf)])
def complete_activity(request: Request, employee_id: str, event_id: str):
    require_employee(request, employee_id)
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

    params = {"lang": _lang_for_request(request, store.employees[employee_id].get("preferred_language"))}
    if changed:
        params["changed"] = changed
    url = f"/employee/{employee_id}?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=303)


# ---------------------------------------------------------------------------
# HTML: HR
# ---------------------------------------------------------------------------


@app.get("/hr")
def hr_page(request: Request, uploaded: int | None = None):
    require_hr(request)
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
            "risk_count": overview["engagement_risk_count"],
        },
    )


@app.post("/hr/upload", dependencies=[Depends(require_csrf)])
async def hr_upload(
    request: Request,
    employees_file: UploadFile | None = File(default=None),
    history_file: UploadFile | None = File(default=None),
):
    """HTML-обёртка над /api/data/upload — форма на странице HR для проверочных
    профилей жюри (см. README, «Как проверить решение»)."""
    require_hr(request)
    added_e, added_h = await _parse_upload(employees_file, history_file)
    return RedirectResponse(url=f"/hr?uploaded={added_e + added_h}", status_code=303)


# ---------------------------------------------------------------------------
# JSON API — для проверки жюри и программного доступа
# ---------------------------------------------------------------------------


@app.get("/api/employees/{employee_id}")
def api_employee(request: Request, employee_id: str):
    require_employee(request, employee_id)
    if employee_id not in store.employees:
        raise HTTPException(status_code=404, detail="not found")
    return engine.recommend(store, employee_id)


@app.post("/api/employees/{employee_id}/explain/{event_id}", dependencies=[Depends(require_csrf)])
async def api_explain(request: Request, employee_id: str, event_id: str):
    from .explain import build_rationale_async

    require_employee(request, employee_id)
    if employee_id not in store.employees:
        raise HTTPException(status_code=404, detail="not found")
    result = engine.recommend(store, employee_id)
    step = next((item for item in result["steps"] if item["event"]["event_id"] == event_id), None)
    if step is None:
        raise HTTPException(status_code=409, detail="Рекомендация изменилась — обновите страницу")
    named_step = {**step, "skills": [
        {**skill, "skill_name": _skill_name(skill["skill_id"])} for skill in step["skills"]
    ]}
    lang = _lang_for_request(request, store.employees[employee_id].get("preferred_language"))
    rationale = await build_rationale_async(result["target_grade"], named_step, lang)
    rationale["tool_labels"] = [
        f"{translate(lang, call['tool'])}: {_skill_name(call['skill_id'])}" for call in rationale["tool_calls"]
    ]
    return rationale


@app.post("/api/employees/{employee_id}/complete/{event_id}", dependencies=[Depends(require_csrf)])
def api_complete(request: Request, employee_id: str, event_id: str):
    require_employee(request, employee_id)
    try:
        record = store.complete_activity(employee_id, event_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="not found") from None
    except InvalidCompletionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"record": record, "profile": engine.recommend(store, employee_id)}


@app.get("/api/hr/overview")
def api_hr_overview(request: Request):
    require_hr(request)
    return engine.hr_overview(store)


@app.post("/api/data/upload", dependencies=[Depends(require_csrf)])
async def api_upload(
    request: Request,
    employees_file: UploadFile | None = File(default=None),
    history_file: UploadFile | None = File(default=None),
):
    """Загрузка дополнительных профилей/истории в формате датасета — для проверочных
    профилей жюри (ТЗ, п.7: «на защите жюри загружает проверочные профили»).
    Принимает employees.json-подобный JSON (объект {"employees": [...]} или просто
    список) и/или activity_history.csv-подобный CSV с теми же колонками."""
    require_hr(request)
    added_employees, added_history = await _parse_upload(employees_file, history_file)
    return {"added_employees": added_employees, "added_history_records": added_history}


@app.get("/health")
def health():
    return {"status": "ok", "employees": len(store.employees), "events": len(store.events)}
