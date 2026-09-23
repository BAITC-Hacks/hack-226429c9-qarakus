from copy import deepcopy

from app import engine
from app.store import DataStore


def profile():
    return {
        "employee_id": "REVIEW_TEST", "full_name": "Review Test", "role": "Backend Engineer",
        "grade": "Middle", "skills": {"SK_SYSTEM_DESIGN": 1}, "last_review_date": "2026-09-01",
    }


def completion(date, event_id="REVIEW_EVENT"):
    return {"employee_id": "REVIEW_TEST", "event_id": event_id, "date": date, "status": "completed"}


def test_history_after_review_applied_once_and_import_order_independent():
    store = DataStore()
    store.events["REVIEW_EVENT"] = {
        "develops_skills": [{"skill_id": "SK_SYSTEM_DESIGN", "gain": 2, "max_level": 4}]
    }
    store.add_employees([profile()])
    assert store.employees["REVIEW_TEST"]["skills"]["SK_SYSTEM_DESIGN"] == 1
    row = completion("2026-09-02")
    assert store.add_history([row]) == 1
    assert store.employees["REVIEW_TEST"]["skills"]["SK_SYSTEM_DESIGN"] == 3
    assert store.add_history([row]) == 0
    store.add_employees([profile()])
    assert store.employees["REVIEW_TEST"]["skills"]["SK_SYSTEM_DESIGN"] == 3
    store.add_employees([{**profile(), "last_review_date": "2026-09-02"}])
    assert store.employees["REVIEW_TEST"]["skills"]["SK_SYSTEM_DESIGN"] == 1


def test_history_before_or_on_review_and_noncompleted_do_not_raise_skills():
    store = DataStore()
    for event_id in ["BEFORE", "ON", "DECLINED"]:
        store.events[event_id] = {"develops_skills": [{"skill_id": "SK_SYSTEM_DESIGN", "gain": 2, "max_level": 5}]}
    store.import_data([profile()], [
        completion("2026-08-31", "BEFORE"), completion("2026-09-01", "ON"),
        {**completion("2026-09-02", "DECLINED"), "status": "declined"},
    ])
    assert store.employees["REVIEW_TEST"]["skills"]["SK_SYSTEM_DESIGN"] == 1


def test_chronological_replay_and_caps_when_history_arrives_out_of_order():
    store = DataStore()
    store.events["EARLY"] = {"develops_skills": [{"skill_id": "SK_SYSTEM_DESIGN", "gain": 1, "max_level": 2}]}
    store.events["LATE"] = {"develops_skills": [{"skill_id": "SK_SYSTEM_DESIGN", "gain": 1, "max_level": 5}]}
    store.import_data([profile()], [completion("2026-09-03", "LATE")])
    store.add_history([completion("2026-09-02", "EARLY")])
    assert store.employees["REVIEW_TEST"]["skills"]["SK_SYSTEM_DESIGN"] == 3


def test_runtime_completion_survives_later_history_upload_without_double_gain():
    store = DataStore()
    employee_id = "E0028"
    step = engine.recommend(store, employee_id)["steps"][0]
    record = store.complete_activity(employee_id, step["event"]["event_id"])
    assert record["date"] == "2026-10-01"
    skills = dict(store.employees[employee_id]["skills"])
    store.add_history([{"employee_id": employee_id, "event_id": "EV_036",
                        "date": "2026-09-01", "status": "declined"}])
    assert store.employees[employee_id]["skills"] == skills


def test_all_seed_recommendations_have_actual_gain_and_completion_matches_preview():
    store = DataStore()
    for employee_id in store.employees:
        result = engine.recommend(store, employee_id)
        for step in result["steps"]:
            assert step["skills"]
            for skill in step["skills"]:
                assert skill["after"] > skill["current"]
    for employee_id in ["E0001", "E0002", "E0028"]:
        result = engine.recommend(store, employee_id)
        step = result["steps"][0]
        before = deepcopy(store.employees[employee_id]["skills"])
        store.complete_activity(employee_id, step["event"]["event_id"])
        updated = engine.recommend(store, employee_id)
        assert updated["readiness_percent"] == step["projected_readiness_percent"]
        assert all(store.employees[employee_id]["skills"][skill_id] >= level for skill_id, level in before.items())


def test_unknown_and_ready_employees_are_not_in_no_available_step_bucket():
    store = DataStore()
    ready = {**profile(), "skills": dict(store.role_profiles[("Backend Engineer", "Senior")]["required_skills"])}
    store.add_employees([ready, {**profile(), "employee_id": "UNKNOWN_TEST", "role": "Unknown"}])
    overview = engine.hr_overview(store)
    assert "UNKNOWN_TEST" in overview["employees_unknown_data"]
    assert "UNKNOWN_TEST" not in overview["employees_without_step"]
    assert "REVIEW_TEST" not in overview["employees_without_step"]
