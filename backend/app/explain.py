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


def _llm_rationale(target_grade: str, step: dict, lang: str, employee_name: str) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        facts = _template_rationale(target_grade, step, lang="en")  # факты в нейтральном виде для модели
        lang_name = {"ru": "русском", "kk": "казахском", "en": "английском"}.get(lang, "русском")
        prompt = (
            f"Ты помогаешь сотруднику {employee_name} понять, почему ему рекомендована активность "
            f"«{step['event']['title']}». Вот проверенные факты (не выдумывай новых, не меняй числа): {facts}. "
            f"Напиши 2-3 коротких предложения на {lang_name} языке, дружелюбно и конкретно объясняющих, "
            f"зачем эта активность нужна именно этому человеку. Упомяни минимум два из фактов."
        )
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            timeout=8,
        )
        text = resp.choices[0].message.content
        return text.strip() if text else None
    except Exception:
        return None


def build_rationale(target_grade: str, step: dict, lang: str, employee_name: str) -> dict:
    template_text = _template_rationale(target_grade, step, lang)
    llm_text = _llm_rationale(target_grade, step, lang, employee_name)
    return {
        "text": llm_text or template_text,
        "source": "llm" if llm_text else "template",
        "facts": template_text,
    }
