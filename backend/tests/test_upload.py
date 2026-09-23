"""Проверка загрузки дополнительных профилей и истории."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import main
from app.store import DataStore


def upload(name: str, content: str) -> UploadFile:
    file = tempfile.SpooledTemporaryFile()
    file.write(content.encode("utf-8"))
    file.seek(0)
    return UploadFile(filename=name, file=file)


def test_invalid_history_does_not_import_profiles(monkeypatch):
    store = DataStore()
    monkeypatch.setattr(main, "store", store)
    profile = {
        "employee_id": "TEST_UPLOAD",
        "full_name": "Test Upload",
        "role": "Backend Engineer",
        "grade": "Middle",
        "skills": {"SK_PYTHON": 3},
    }
    profiles = upload("employees.json", json.dumps({"employees": [profile]}))
    history = upload("history.csv", "employee_id,event_id,date,status\nTEST_UPLOAD,UNKNOWN,2026-09-01,completed\n")
    before = len(store.history)

    with pytest.raises(HTTPException) as error:
        asyncio.run(main._parse_upload(profiles, history))

    assert error.value.status_code == 400
    assert "TEST_UPLOAD" not in store.employees
    assert len(store.history) == before


def test_valid_profiles_and_history_import_together(monkeypatch):
    store = DataStore()
    monkeypatch.setattr(main, "store", store)
    profile = {
        "employee_id": "TEST_UPLOAD",
        "full_name": "Test Upload",
        "role": "Backend Engineer",
        "grade": "Middle",
        "skills": {"SK_PYTHON": 3},
    }
    profiles = upload("employees.json", json.dumps({"employees": [profile]}))
    history = upload("history.csv", "employee_id,event_id,date,status\nTEST_UPLOAD,EV_036,2026-09-01,declined\n")

    assert asyncio.run(main._parse_upload(profiles, history)) == (1, 1)
    assert store.employees["TEST_UPLOAD"]["full_name"] == "Test Upload"
    assert store.history_for_employee("TEST_UPLOAD")[0]["record_id"].startswith("UPLOAD")
