"""Генерация текста объяснения рекомендации.

Факты (разрыв, критичность, история) всегда считает engine.py — детерминированно.
Этот модуль только формулирует их в текст. Гарантированный путь — шаблон без каких-либо
внешних вызовов (работает без интернета и без ключей — важно для воспроизводимости).
Если задан OPENAI_API_KEY — тот же набор фактов передаётся модели, чтобы получить более
естественную и локализованную (kk/ru/en, по employee.preferred_language) формулировку.
При любой ошибке вызова LLM (нет ключа, нет сети, таймаут) — используется шаблон,
рекомендация никогда не остаётся без обоснования.
"""

from __future__ import annotations

import os

_LANG_LABELS = {
    "ru": {"current": "сейчас", "required": "требуется", "critical": "критический навык для перехода",
           "no_history": "истории пропусков по активностям этого навыка нет",
           "history": "по истории: {completed} завершено, {avoided} пропущено/отклонено по активностям этого навыка",
           "avoided_event": "внимание: именно это мероприятие сотрудник уже пропускал/отклонял ранее — стоит предложить альтернативный формат"},
    "kk": {"current": "қазір", "required": "қажет", "critical": "ауысу үшін маңызды дағды",
           "no_history": "бұл дағды бойынша өткізіп алулар тарихы жоқ",
           "history": "тарих бойынша: {completed} аяқталды, {avoided} өткізіп алынды/бас тартылды",
           "avoided_event": "назар аударыңыз: қызметкер дәл осы іс-шараны бұрын өткізіп алған/бас тартқан — балама формат ұсынған жөн"},
    "en": {"current": "now", "required": "required", "critical": "critical skill for promotion",
           "no_history": "no history of skipping activities for this skill",
           "history": "history: {completed} completed, {avoided} skipped/declined for this skill",
           "avoided_event": "note: the employee already skipped/declined this exact event before — consider an alternative format"},
}


def _template_rationale(target_grade: str, step: dict, lang: str = "ru") -> str:
    labels = _LANG_LABELS.get(lang, _LANG_LABELS["ru"])
    parts = []
    for s in step["skills"]:
        hist = s["history"]
        avoided = hist["declined"] + hist["no_show"] + hist["dropped"]
        bit = f"{s['skill_id']}: {labels['current']} {s['current']}, {labels['required']} {s['required']} ({target_grade})"
        if s["critical"]:
            bit += f" — {labels['critical']}"
        bit += ". " + (
            labels["history"].format(completed=hist["completed"], avoided=avoided) if avoided or hist["completed"]
            else labels["no_history"]
        )
        if s.get("was_avoided_before"):
            bit += ". " + labels["avoided_event"]
        parts.append(bit)
    return " | ".join(parts)


def _llm_agentic_rationale(target_grade: str, step: dict, lang: str, employee_name: str) -> str | None:
    """Agentic-слой: модель сама решает, нужно ли ей узнать историю участия или
    альтернативные мероприятия, и запрашивает это через function calling, вместо
    того чтобы всё было заранее вписано в промпт. Числа она получает только из
    инструментов/фактов, а не придумывает — если инструмент не вызван, соответствующая
    деталь просто не попадёт в текст.

    Полностью опционально: при отсутствии ключа, сетевой ошибке или любом сбое во время
    цикла — возвращает None, и build_rationale() падает обратно на детерминированный
    шаблон (см. модульный docstring)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import json as _j

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        skills_by_id = {s["skill_id"]: s for s in step["skills"]}

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_skill_history",
                    "description": (
                        "История участия сотрудника в активностях, развивающих указанный навык: "
                        "сколько раз завершено/отклонено/пропущено."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"skill_id": {"type": "string", "enum": list(skills_by_id.keys())}},
                        "required": ["skill_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_alternative_events",
                    "description": "Альтернативные мероприятия, развивающие тот же навык, если основное сотрудник уже избегал.",
                    "parameters": {
                        "type": "object",
                        "properties": {"skill_id": {"type": "string", "enum": list(skills_by_id.keys())}},
                        "required": ["skill_id"],
                    },
                },
            },
        ]

        def call_tool(name: str, args: dict):
            s = skills_by_id.get(args.get("skill_id"))
            if not s:
                return {"error": "unknown skill_id"}
            if name == "get_skill_history":
                return s["history"]
            if name == "get_alternative_events":
                return s.get("alternative_events", [])
            return {"error": "unknown tool"}

        lang_name = {"ru": "русском", "kk": "казахском", "en": "английском"}.get(lang, "русском")
        skills_summary = "; ".join(
            f"{sid}: сейчас {s['current']}, требуется {s['required']} для {target_grade}"
            + (" (критично для перехода)" if s["critical"] else "")
            for sid, s in skills_by_id.items()
        )
        messages: list = [
            {
                "role": "system",
                "content": (
                    "Ты объясняешь сотруднику HR-платформы, почему ему рекомендована активность развития. "
                    "У тебя есть инструменты, чтобы узнать историю участия сотрудника и альтернативные "
                    "мероприятия — вызови их, если это сделает объяснение точнее и честнее. Никогда не "
                    "придумывай цифры, которых нет в предоставленных фактах или в ответах инструментов."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Сотрудник: {employee_name}. Рекомендуемое мероприятие: «{step['event']['title']}». "
                    f"Разрывы по навыкам: {skills_summary}. Напиши 2-3 коротких предложения на {lang_name} "
                    f"языке, объясняющих рекомендацию конкретно для этого человека."
                ),
            },
        ]

        for _ in range(3):
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=messages,
                tools=tools,
                timeout=8,
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                )
                for tc in msg.tool_calls:
                    args = _j.loads(tc.function.arguments or "{}")
                    result = call_tool(tc.function.name, args)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": _j.dumps(result, ensure_ascii=False)})
                continue
            return (msg.content or "").strip() or None
        return None
    except Exception:
        return None


def build_rationale(target_grade: str, step: dict, lang: str, employee_name: str) -> dict:
    template_text = _template_rationale(target_grade, step, lang)
    llm_text = _llm_agentic_rationale(target_grade, step, lang, employee_name)
    return {
        "text": llm_text or template_text,
        "source": "llm-agentic" if llm_text else "template",
        "facts": template_text,
    }
