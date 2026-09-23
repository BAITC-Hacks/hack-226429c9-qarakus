"""Локализация интерфейса на kk/ru/en.

Дизайн-решение: язык страницы сотрудника берётся из его `preferred_language` —
в датасете это поле прямо описано как "UI language preference" (см. README датасета).
Значит язык интерфейса определяется данными, а не отдельной настройкой — это и есть
честная связь с датасетом, а не декоративная фича. HR-панель и страница входа не
привязаны к конкретному сотруднику, поэтому там используется переключатель
(параметр ?lang=, сохраняется в cookie).

Объяснения рекомендаций (explain.py) локализуются отдельно и по тому же принципу —
это было сделано раньше и не меняется здесь.
"""

from __future__ import annotations

SUPPORTED = ("ru", "kk", "en")
DEFAULT = "ru"

_T: dict[str, dict[str, str]] = {
    "brand": {"ru": "Career Quest", "kk": "Career Quest", "en": "Career Quest"},
    "nav_hr": {"ru": "HR-панель", "kk": "HR тақтасы", "en": "HR panel"},
    "nav_switch_employee": {"ru": "Сменить сотрудника", "kk": "Қызметкерді ауыстыру", "en": "Switch employee"},
    "index_title": {"ru": "Career Quest", "kk": "Career Quest", "en": "Career Quest"},
    "index_subtitle": {
        "ru": "Упрощённая имитация входа: сотрудник вводит свой ID и видит только свой профиль — публичного каталога чужих профилей нет.",
        "kk": "Кірудің қарапайым имитациясы: қызметкер өз ID-ін енгізеді және тек өз профилін көреді — басқалардың профильдерінің ортақ каталогы жоқ.",
        "en": "Simplified login: the employee enters their own ID and sees only their profile — there is no public directory of other profiles.",
    },
    "index_placeholder": {
        "ru": "Ваш ID, например E0028",
        "kk": "Сіздің ID, мысалы E0028",
        "en": "Your ID, e.g. E0028",
    },
    "index_login_btn": {"ru": "Войти", "kk": "Кіру", "en": "Log in"},
    "index_demo_hint": {
        "ru": "Демо для жюри: например E0028 (пример из самого ТЗ), E0001, E0100.",
        "kk": "Қазылар үшін демо: мысалы E0028 (ТЗ-дегі мысал), E0001, E0100.",
        "en": "Demo for judges: e.g. E0028 (the example from the spec itself), E0001, E0100.",
    },
    "index_hr_link": {"ru": "Войти как HR →", "kk": "HR ретінде кіру →", "en": "Log in as HR →"},
    "not_found": {
        "ru": "Сотрудник «{id}» не найден. Проверьте ID.",
        "kk": "«{id}» қызметкері табылмады. ID-ді тексеріңіз.",
        "en": "Employee \"{id}\" not found. Check the ID.",
    },
    "goal_set": {"ru": "Цель:", "kk": "Мақсат:", "en": "Goal:"},
    "goal_not_set": {
        "ru": "Цель не задана — считаем следующий грейд в текущей роли",
        "kk": "Мақсат қойылмаған — ағымдағы рөлдегі келесі грейдті есептейміз",
        "en": "No goal set — using the next grade in the current role",
    },
    "grade_label": {"ru": "грейд", "kk": "грейд", "en": "grade"},
    "tenure": {"ru": "стаж", "kk": "өтіл", "en": "tenure"},
    "months": {"ru": "мес.", "kk": "ай", "en": "mo."},
    "readiness_title": {"ru": "Готовность к грейду", "kk": "Грейдке дайындық", "en": "Readiness for grade"},
    "readiness_caption": {
        "ru": "Готовность = доля требований грейда {grade}, которые уже выполнены (навыков без разрыва / всего требуемых навыков). Как считаются сами разрывы — ниже.",
        "kk": "Дайындық = {grade} грейдінің талаптарының қанша бөлігі орындалғаны (олқылықсыз дағдылар / барлық қажетті дағдылар). Олқылықтардың өзі қалай есептелетіні — төменде.",
        "en": "Readiness = share of {grade} grade requirements already met (skills without a gap / all required skills). How the gaps themselves are calculated is shown below.",
    },
    "gaps_title": {"ru": "Разрывы по навыкам", "kk": "Дағдылар бойынша олқылықтар", "en": "Skill gaps"},
    "gaps_none": {
        "ru": "Все требования грейда {grade} выполнены — рекомендаций по разрывам нет.",
        "kk": "{grade} грейдінің барлық талаптары орындалды — олқылықтар бойынша ұсыныстар жоқ.",
        "en": "All requirements for grade {grade} are met — no gap-based recommendations.",
    },
    "critical_badge": {"ru": "критично для перехода", "kk": "ауысу үшін маңызды", "en": "critical for promotion"},
    "gap_label": {"ru": "разрыв", "kk": "олқылық", "en": "gap"},
    "steps_title": {"ru": "Рекомендованные следующие шаги", "kk": "Ұсынылған келесі қадамдар", "en": "Recommended next steps"},
    "steps_none": {
        "ru": "Подходящих добровольных активностей под текущие разрывы не найдено.",
        "kk": "Ағымдағы олқылықтарға сәйкес ерікті іс-шаралар табылмады.",
        "en": "No matching voluntary activities found for the current gaps.",
    },
    "complete_btn": {"ru": "Отметить выполненным", "kk": "Орындалды деп белгілеу", "en": "Mark as completed"},
    "changed_banner_title": {
        "ru": "Активность отмечена выполненной. Что изменилось:",
        "kk": "Іс-шара орындалды деп белгіленді. Не өзгерді:",
        "en": "Activity marked as completed. What changed:",
    },
    "rationale_source_llm": {
        "ru": "LLM-агент (с function calling)",
        "kk": "LLM-агент (function calling арқылы)",
        "en": "LLM agent (with function calling)",
    },
    "rationale_source_template": {
        "ru": "детерминированный шаблон",
        "kk": "детерминирленген үлгі",
        "en": "deterministic template",
    },
    "rationale_source_label": {"ru": "источник обоснования:", "kk": "негіздеме көзі:", "en": "rationale source:"},
    "history_title": {"ru": "История участия", "kk": "Қатысу тарихы", "en": "Participation history"},
    "history_date": {"ru": "Дата", "kk": "Күні", "en": "Date"},
    "history_activity": {"ru": "Активность", "kk": "Іс-шара", "en": "Activity"},
    "history_status": {"ru": "Статус", "kk": "Мәртебе", "en": "Status"},
    "hr_title": {"ru": "HR-панель", "kk": "HR тақтасы", "en": "HR panel"},
    "hr_total": {"ru": "Всего сотрудников:", "kk": "Барлық қызметкерлер:", "en": "Total employees:"},
    "hr_upload_title": {
        "ru": "Загрузить проверочные профили (для жюри)",
        "kk": "Тексеру профильдерін жүктеу (қазылар үшін)",
        "en": "Upload verification profiles (for judges)",
    },
    "hr_upload_desc": {
        "ru": "Формат — как в стартовом датасете: JSON вида employees.json и/или CSV вида activity_history.csv. Оба поля опциональны, можно загрузить только один файл.",
        "kk": "Формат — бастапқы датасеттегідей: employees.json түріндегі JSON және/немесе activity_history.csv түріндегі CSV. Екі өріс те міндетті емес, тек бір файл жүктеуге болады.",
        "en": "Format — same as the starter dataset: JSON like employees.json and/or CSV like activity_history.csv. Both fields are optional, you can upload just one file.",
    },
    "hr_upload_success": {"ru": "Загружено записей:", "kk": "Жүктелген жазбалар:", "en": "Records uploaded:"},
    "hr_upload_profiles_label": {"ru": "Профили (JSON)", "kk": "Профильдер (JSON)", "en": "Profiles (JSON)"},
    "hr_upload_history_label": {"ru": "История (CSV)", "kk": "Тарих (CSV)", "en": "History (CSV)"},
    "hr_upload_btn": {"ru": "Загрузить", "kk": "Жүктеу", "en": "Upload"},
    "hr_lagging_title": {
        "ru": "Чаще всего проседающие навыки",
        "kk": "Жиі төмендейтін дағдылар",
        "en": "Most frequently lagging skills",
    },
    "hr_lagging_of": {"ru": "из", "kk": "ішінен", "en": "of"},
    "hr_lagging_avg_gap": {"ru": "средний разрыв", "kk": "орташа олқылық", "en": "avg gap"},
    "hr_lowest_readiness_title": {
        "ru": "Ниже всего готовность к следующему грейду",
        "kk": "Келесі грейдке дайындығы ең төмен",
        "en": "Lowest readiness for the next grade",
    },
    "hr_without_step_title": {
        "ru": "Без рекомендованного шага",
        "kk": "Ұсынылған қадамы жоқ",
        "en": "Without a recommended step",
    },
    "hr_without_step_all_good": {
        "ru": "У всех сотрудников есть хотя бы один рекомендованный шаг.",
        "kk": "Барлық қызметкерлерде кемінде бір ұсынылған қадам бар.",
        "en": "Every employee has at least one recommended step.",
    },
    "hr_risk_title": {
        "ru": "Риск снижения вовлечённости",
        "kk": "Тартылымдылықтың төмендеу қаупі",
        "en": "Engagement risk",
    },
    "hr_risk_caption": {
        "ru": "Эвристика, не строгий прогноз оттока (нет данных о зарплате/удовлетворённости): часто отказывается/пропускает + готовность к грейду стагнирует.",
        "kk": "Эвристика, қатаң кету болжамы емес (жалақы/қанағаттану деректері жоқ): жиі бас тартады/өткізіп алады + грейдке дайындық тоқтап тұр.",
        "en": "Heuristic, not a strict attrition forecast (no salary/satisfaction data): frequent declines/no-shows combined with stagnant grade readiness.",
    },
    "hr_risk_none": {
        "ru": "Ни у кого нет одновременно высокой доли отказов и низкой готовности.",
        "kk": "Ешкімде бас тартулардың жоғары үлесі мен төмен дайындық бір мезгілде жоқ.",
        "en": "No one currently has both a high avoidance rate and low readiness.",
    },
    "hr_risk_avoidance": {"ru": "доля отказов/пропусков", "kk": "бас тарту/өткізіп алу үлесі", "en": "avoidance rate"},
    "hr_participation_title": {"ru": "Участие по активностям", "kk": "Іс-шаралар бойынша қатысу", "en": "Participation by activity"},
    "hr_col_activity": {"ru": "Активность", "kk": "Іс-шара", "en": "Activity"},
    "hr_col_completed": {"ru": "Завершено", "kk": "Аяқталды", "en": "Completed"},
    "hr_col_declined": {"ru": "Отказ", "kk": "Бас тартылды", "en": "Declined"},
    "hr_col_no_show": {"ru": "Пропуск", "kk": "Өткізіп алынды", "en": "No-show"},
    "hr_col_dropped": {"ru": "Бросил", "kk": "Тоқтатты", "en": "Dropped"},
}


def translate(lang: str, key: str, **fmt) -> str:
    lang = lang if lang in SUPPORTED else DEFAULT
    entry = _T.get(key)
    if entry is None:
        return key
    text = entry.get(lang, entry.get(DEFAULT, key))
    return text.format(**fmt) if fmt else text


def resolve_lang(*candidates: str | None) -> str:
    for c in candidates:
        if c in SUPPORTED:
            return c
    return DEFAULT
