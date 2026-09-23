"""Подписанная сессия, проверка роли и CSRF для демо и локального пилота."""

import json
import os
import secrets

from fastapi import HTTPException, Request


def demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "true").lower() == "true"


def authenticate(username: str, password: str) -> dict | None:
    hr_password = os.environ.get("HR_PASSWORD") or ("hr-demo" if demo_mode() else "")
    if username == "hr":
        if hr_password and secrets.compare_digest(password.encode(), hr_password.encode()):
            return {"role": "hr", "employee_id": None}
        return None
    configured = os.environ.get("EMPLOYEE_PASSWORDS_JSON")
    try:
        passwords = json.loads(configured) if configured else ({"E0028": "employee-demo"} if demo_mode() else {})
    except json.JSONDecodeError:
        return None
    if not isinstance(passwords, dict):
        return None
    expected = passwords.get(username, "")
    if isinstance(expected, str) and expected and secrets.compare_digest(password.encode(), expected.encode()):
        return {"role": "employee", "employee_id": username}
    return None


def require_employee(request: Request, employee_id: str) -> None:
    role = request.session.get("role")
    if not role:
        raise HTTPException(status_code=401, detail="Войдите в систему")
    if role != "hr" and request.session.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="Доступен только ваш профиль")


def require_hr(request: Request) -> None:
    role = request.session.get("role")
    if not role:
        raise HTTPException(status_code=401, detail="Войдите в систему")
    if role != "hr":
        raise HTTPException(status_code=403, detail="Действие доступно только HR")


async def require_csrf(request: Request) -> None:
    expected = request.session.get("csrf_token", "")
    supplied = request.headers.get("x-csrf-token")
    if supplied is None:
        supplied = (await request.form()).get("csrf_token")
    if (not expected or not isinstance(supplied, str)
            or not secrets.compare_digest(expected.encode(), supplied.encode())):
        raise HTTPException(status_code=403, detail="Сессия формы устарела. Обновите страницу и повторите действие")
