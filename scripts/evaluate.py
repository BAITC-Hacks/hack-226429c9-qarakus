"""Воспроизводимая проверка движка на исходных и демонстрационных профилях."""

import csv
import hashlib
import json
import sys
from pathlib import Path


def evaluate() -> dict:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "backend"))
    from app import engine
    from app.store import SEED_DIR, DataStore

    store = DataStore()
    checks = []

    def check(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    results = {employee_id: engine.recommend(store, employee_id) for employee_id in store.employees}
    steps = [step for result in results.values() for step in result["steps"]]
    check("at_most_three_steps_per_employee", all(len(result["steps"]) <= 3 for result in results.values()))
    check("all_recommended_events_voluntary", all(not step["event"].get("mandatory") for step in steps))
    check("all_recommended_skills_have_positive_gain", all(
        step["skills"] and all(skill["after"] > skill["current"] for skill in step["skills"])
        for step in steps
    ))
    check("all_recommended_events_available", all(
        engine.event_is_available(store, store.employees[employee_id], step["event"],
                                  result["target_role"], result["target_grade"])
        for employee_id, result in results.items() for step in result["steps"]
    ))
    matched_previews = 0
    for employee_id, result in results.items():
        if not result["steps"]:
            continue
        step = result["steps"][0]
        before = dict(store.employees[employee_id]["skills"])
        store.complete_activity(employee_id, step["event"]["event_id"])
        after = engine.recommend(store, employee_id)
        matches = after["readiness_percent"] == step["projected_readiness_percent"]
        matches = matches and all(
            store.employees[employee_id]["skills"][skill["skill_id"]] == skill["after"]
            for skill in step["skills"]
        )
        matches = matches and all(store.employees[employee_id]["skills"][skill_id] >= level
                                  for skill_id, level in before.items())
        matched_previews += int(matches)
    employees_with_steps = sum(bool(result["steps"]) for result in results.values())
    check("first_step_preview_matches_completion_without_skill_decrease", matched_previews == employees_with_steps)

    demo = root / "docs" / "demo"
    profiles = json.loads((demo / "employees.json").read_text(encoding="utf-8"))["employees"]
    with (demo / "activity_history.csv").open(encoding="utf-8", newline="") as source:
        history = list(csv.DictReader(source))
    demo_store = DataStore()
    demo_store.import_data(profiles, history)
    check("duplicate_history_has_no_effect", demo_store.add_history(history) == 0)
    trap = engine.recommend(demo_store, "DEMO_TRAP")
    first_step = trap["steps"][0]
    baseline = min(trap["gaps"], key=lambda skill: (skill["current"], skill["skill_id"]))["skill_id"]
    selected = first_step["skills"][0]["skill_id"]
    check("critical_skill_selected_over_lowest_skill_baseline", selected == "SK_SYSTEM_DESIGN"
          and baseline == "SK_PUBLIC_SPEAKING")
    demo_store.complete_activity("DEMO_TRAP", first_step["event"]["event_id"])
    after = engine.recommend(demo_store, "DEMO_TRAP")["readiness_percent"]
    check("demo_readiness_88_to_94", trap["readiness_percent"] == 88 and after == 94)
    history_result = engine.recommend(demo_store, "DEMO_HISTORY")
    check("post_review_history_closes_gap", history_result["readiness_percent"] == 100
          and not history_result["steps"])
    unknown = engine.recommend(demo_store, "DEMO_UNKNOWN")
    check("unknown_role_is_not_false_100_percent", unknown["readiness_percent"] is None)
    sources = sorted(SEED_DIR.glob("*.json")) + [SEED_DIR / "activity_history.csv",
                                              demo / "employees.json", demo / "activity_history.csv"]
    return {
        "schema_version": 1,
        "scope": "Deterministic synthetic-data checks; not a business-impact or LLM-quality benchmark",
        "scenario_date": store.as_of_date,
        "external_api_calls": 0,
        "seed": {"employees": len(results), "events": len(store.events), "skills": len(store.skills_catalog),
                 "recommended_steps": len(steps), "employees_with_steps": employees_with_steps,
                 "first_step_previews_matching_completion": matched_previews},
        "demonstration": {"lowest_skill_baseline": baseline, "selected_skill": selected,
                          "selected_event": first_step["event"]["event_id"],
                          "readiness_before": trap["readiness_percent"], "readiness_after": after,
                          "unknown_role_readiness": unknown["readiness_percent"]},
        "input_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in sources},
        "checks": checks,
        "passed": all(result["passed"] for result in checks),
    }


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
