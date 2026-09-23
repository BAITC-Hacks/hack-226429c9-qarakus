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
        self._load_seed()

    # ---------- загрузка стартового датасета ----------

    def _load_seed(self) -> None:
        skills_data = json.loads((SEED_DIR / "skills.json").read_text(encoding="utf-8"))
        self.skills_catalog = {s["skill_id"]: s for s in skills_data["skills"]}
        for rp in skills_data["role_profiles"]:
            self.role_profiles[(rp["role"], rp["grade"])] = rp

        events_data = json.loads((SEED_DIR / "events.json").read_text(encoding="utf-8"))
        self.events = {e["event_id"]: e for e in events_data["events"]}

        employees_data = json.loads((SEED_DIR / "employees.json").read_text(encoding="utf-8"))
        for e in employees_data["employees"]:
            self.employees[e["employee_id"]] = e

        with open(SEED_DIR / "activity_history.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.history.append(row)
                self._next_record_id += 1

    # ---------- расширение данными жюри/загрузки ----------

    def add_employees(self, employees: list[dict]) -> int:
        """Добавляет/обновляет профили сотрудников (формат employees.json → employees[])."""
        with self._lock:
            for e in employees:
                self.employees[e["employee_id"]] = e
        return len(employees)

    def add_history(self, rows: list[dict]) -> int:
        """Добавляет записи истории участия (формат activity_history.csv)."""
        with self._lock:
            for r in rows:
                r.setdefault("record_id", f"UPLOAD{self._next_record_id:06d}")
                self._next_record_id += 1
                self.history.append(r)
        return len(rows)

    def import_data(self, employees: list[dict], history: list[dict]) -> tuple[int, int]:
        """Применяет проверенные профили и историю одной операцией."""
        with self._lock:
            for employee in employees:
                self.employees[employee["employee_id"]] = employee
            for row in history:
                record = dict(row)
                if not record.get("record_id"):
                    record["record_id"] = f"UPLOAD{self._next_record_id:06d}"
                self._next_record_id += 1
                self.history.append(record)
        return len(employees), len(history)

    def complete_activity(self, employee_id: str, event_id: str) -> dict:
        """Отмечает активность выполненной: пишет запись в историю и поднимает навыки
        по правилу датасета (gain, не выше max_level).

        Проверяет те же ограничения доступности, что и движок рекомендаций."""
        import datetime

        from .engine import event_is_available, target_for_employee

        emp = self.employees.get(employee_id)
        event = self.events.get(event_id)
        if emp is None or event is None:
            raise KeyError("employee or event not found")
        with self._lock:
            target_role, target_grade, _ = target_for_employee(self, emp)
            if not event_is_available(self, emp, event, target_role, target_grade):
                raise InvalidCompletionError(f"{event_id} недоступно для {employee_id} или уже выполнено")
            record = {
                "record_id": f"RUNTIME{self._next_record_id:06d}",
                "employee_id": employee_id,
                "event_id": event_id,
                "date": datetime.date.today().isoformat(),
                "due_date": "",
                "status": "completed",
                "completion_pct": "100",
                "score": "",
                "feedback_rating": "",
                "assigned_by": "self",
            }
            self._next_record_id += 1
            self.history.append(record)

            for dev in event.get("develops_skills", []):
                skill_id, gain, max_level = dev["skill_id"], dev["gain"], dev["max_level"]
                current = emp["skills"].get(skill_id, 0)
                # Навык не должен ПОНИЖАТЬСЯ, даже если max_level этого конкретного
                # мероприятия ниже текущего уровня сотрудника (он мог быть достигнут
                # через другую активность/грейд). max(...) — явная защита от регресса,
                # min(...) — правило датасета «не выше max_level» для самого прироста.
                emp["skills"][skill_id] = max(current, min(max_level, current + gain))

        return record

    # ---------- выборки ----------

    def history_for_employee(self, employee_id: str) -> list[dict]:
        return [r for r in self.history if r["employee_id"] == employee_id]

    def completed_event_ids(self, employee_id: str) -> set[str]:
        return {r["event_id"] for r in self.history_for_employee(employee_id) if r["status"] == "completed"}


store = DataStore()
