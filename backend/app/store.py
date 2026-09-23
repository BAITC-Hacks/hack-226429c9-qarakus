"""Хранилище данных Career Quest.

Загружает стартовый датасет (employees.json, events.json, skills.json,
activity_history.csv) и держит его в памяти процесса. Поддерживает добавление
дополнительных профилей/истории в том же формате — это нужно для проверочных
профилей жюри (см. ТЗ, п.7 «Тестовые профили») и для отметки выполненных
активностей во время работы приложения.

Хранение в памяти, а не в БД — осознанное упрощение под ограничение «запуск
одной командой» и 5 часов разработки. Ограничение явно указано в README.
"""

from __future__ import annotations

import csv
import json
import threading
from copy import deepcopy
from pathlib import Path

SEED_DIR = Path(__file__).parent / "data" / "seed"

GRADE_ORDER = ["Junior", "Middle", "Senior", "Lead"]


class InvalidCompletionError(ValueError):
    """Активность не подходит сотруднику или не может быть отмечена повторно."""


class DataStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.skills_catalog: dict[str, dict] = {}
        self.role_profiles: dict[tuple[str, str], dict] = {}
        self.events: dict[str, dict] = {}
        self.employees: dict[str, dict] = {}
        self.history: list[dict] = []
        self._next_record_id = 1
        self._assessed_skills: dict[str, dict] = {}
        self._runtime_records: set[str] = set()
        self._load_seed()

    # ---------- загрузка стартового датасета ----------

    def _load_seed(self) -> None:
        skills_data = json.loads((SEED_DIR / "skills.json").read_text(encoding="utf-8"))
        self.as_of_date = skills_data["meta"]["as_of_date"]
        self.skills_catalog = {s["skill_id"]: s for s in skills_data["skills"]}
        for rp in skills_data["role_profiles"]:
            self.role_profiles[(rp["role"], rp["grade"])] = rp

        events_data = json.loads((SEED_DIR / "events.json").read_text(encoding="utf-8"))
        self.events = {e["event_id"]: e for e in events_data["events"]}

        employees_data = json.loads((SEED_DIR / "employees.json").read_text(encoding="utf-8"))
        with open(SEED_DIR / "activity_history.csv", newline="", encoding="utf-8") as f:
            history = list(csv.DictReader(f))
        self.import_data(employees_data["employees"], history)

    # ---------- расширение данными жюри/загрузки ----------

    def add_employees(self, employees: list[dict]) -> int:
        """Добавляет/обновляет профили сотрудников (формат employees.json → employees[])."""
        return self.import_data(employees, [])[0]

    def add_history(self, rows: list[dict]) -> int:
        """Добавляет записи истории участия (формат activity_history.csv)."""
        return self.import_data([], rows)[1]

    def import_data(self, employees: list[dict], history: list[dict]) -> tuple[int, int]:
        """Применяет проверенные профили и историю одной операцией."""
        with self._lock:
            affected = set()
            for employee in employees:
                employee_id = employee["employee_id"]
                self.employees[employee_id] = deepcopy(employee)
                self._assessed_skills[employee_id] = dict(employee["skills"])
                affected.add(employee_id)
            replaced_ids = {employee["employee_id"] for employee in employees}
            self._runtime_records.difference_update(
                row["record_id"] for row in self.history if row["employee_id"] in replaced_ids
            )
            known_rows = {self._history_key(row) for row in self.history}
            added = 0
            for row in history:
                key = self._history_key(row)
                if key in known_rows:
                    continue
                record = dict(row)
                if not record.get("record_id"):
                    record["record_id"] = f"UPLOAD{self._next_record_id:06d}"
                self._next_record_id += 1
                self.history.append(record)
                known_rows.add(key)
                affected.add(record["employee_id"])
                added += 1
            for employee_id in affected:
                self._refresh_skills(employee_id)
        return len(employees), added

    @staticmethod
    def _history_key(row: dict) -> tuple:
        return tuple(row[field] for field in ("employee_id", "event_id", "date", "status"))

    @staticmethod
    def apply_skill_gain(skills: dict, event: dict) -> None:
        for development in event.get("develops_skills", []):
            skill_id = development["skill_id"]
            current = skills.get(skill_id, 0)
            skills[skill_id] = max(current, min(development["max_level"], current + development["gain"]))

    def _refresh_skills(self, employee_id: str) -> None:
        """Восстанавливает навыки из оценки и завершений после неё, без двойного прироста."""
        employee = self.employees.get(employee_id)
        if employee is None:
            return
        skills = dict(self._assessed_skills[employee_id])
        reviewed = employee.get("last_review_date")
        completed = set()
        for row in sorted(self.history_for_employee(employee_id), key=lambda record: record["date"]):
            event_id = row["event_id"]
            if row["status"] != "completed" or event_id not in self.events:
                continue
            if event_id in completed and event_id != "EV_036":
                continue
            completed.add(event_id)
            if (reviewed and row["date"] > reviewed) or row["record_id"] in self._runtime_records:
                self.apply_skill_gain(skills, self.events[event_id])
        employee["skills"] = skills

    def complete_activity(self, employee_id: str, event_id: str) -> dict:
        """Отмечает активность выполненной: пишет запись в историю и поднимает навыки
        по правилу датасета (gain, не выше max_level).

        Проверяет те же ограничения доступности, что и движок рекомендаций."""
        from .engine import event_is_available, target_for_employee

        with self._lock:
            emp = self.employees.get(employee_id)
            event = self.events.get(event_id)
            if emp is None or event is None:
                raise KeyError("employee or event not found")
            target_role, target_grade, _ = target_for_employee(self, emp)
            if not event_is_available(self, emp, event, target_role, target_grade):
                raise InvalidCompletionError(f"{event_id} недоступно для {employee_id} или уже выполнено")
            record = {
                "record_id": f"RUNTIME{self._next_record_id:06d}",
                "employee_id": employee_id,
                "event_id": event_id,
                "date": self.as_of_date,
                "due_date": "",
                "status": "completed",
                "completion_pct": "100",
                "score": "",
                "feedback_rating": "",
                "assigned_by": "self",
            }
            self._next_record_id += 1
            self.history.append(record)
            self._runtime_records.add(record["record_id"])
            self.apply_skill_gain(emp["skills"], event)

        return record

    # ---------- выборки ----------

    def history_for_employee(self, employee_id: str) -> list[dict]:
        return [r for r in self.history if r["employee_id"] == employee_id]

    def completed_event_ids(self, employee_id: str) -> set[str]:
        return {r["event_id"] for r in self.history_for_employee(employee_id) if r["status"] == "completed"}


store = DataStore()
