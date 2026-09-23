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
    "language_label": {"ru": "Язык интерфейса", "kk": "Интерфейс тілі", "en": "Interface language"},
    "index_title": {"ru": "Career Quest", "kk": "Career Quest", "en": "Career Quest"},
    "index_eyebrow": {"ru": "Навигатор развития", "kk": "Даму навигаторы", "en": "Career development navigator"},
    "index_headline": {
        "ru": "Следующий шаг в карьере — понятнее.",
        "kk": "Мансаптағы келесі қадам — айқынырақ.",
        "en": "Make your next career step clearer.",
    },
    "index_subtitle": {
        "ru": "Посмотрите, какие навыки важны для следующего грейда и какая добровольная активность поможет двигаться дальше.",
        "kk": "Келесі грейдке қандай дағдылар маңызды екенін және қай ерікті іс-шара алға жылжуға көмектесетінін көріңіз.",
        "en": "See which skills matter for your next grade and which voluntary activity can help you progress.",
    },
    "index_step_profile": {"ru": "Ваш профиль", "kk": "Сіздің профиліңіз", "en": "Your profile"},
    "index_step_gaps": {"ru": "Разрывы навыков", "kk": "Дағды олқылықтары", "en": "Skill gaps"},
    "index_step_action": {"ru": "Следующий шаг", "kk": "Келесі қадам", "en": "Next step"},
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
    "not_enough_data": {
        "ru": "Недостаточно данных: роль «{role}» и/или грейд «{grade}» не найдены в справочнике грейдов "
        "(role_profiles). Готовность и разрывы не могут быть посчитаны — проверьте, что эти значения "
        "совпадают со справочником skills.json.",
        "kk": "Деректер жеткіліксіз: «{role}» рөлі және/немесе «{grade}» грейді грейд анықтамалығында "
        "(role_profiles) табылмады. Дайындық пен олқылықтарды есептеу мүмкін емес — skills.json "
        "анықтамалығымен сәйкестігін тексеріңіз.",
        "en": "Not enough data: role \"{role}\" and/or grade \"{grade}\" were not found in the grade "
        "reference (role_profiles). Readiness and gaps cannot be computed — check that these values "
        "match the skills.json reference.",
    },
    "gap_label": {"ru": "разрыв", "kk": "олқылық", "en": "gap"},
    "gaps_show_all": {"ru": "Показать все разрывы", "kk": "Барлық олқылықтарды көрсету", "en": "Show all skill gaps"},
    "steps_title": {"ru": "Рекомендованные следующие шаги", "kk": "Ұсынылған келесі қадамдар", "en": "Recommended next steps"},
    "steps_intro": {
        "ru": "Начните с одного подходящего шага. Каждая рекомендация связана с требованиями вашего следующего грейда.",
        "kk": "Өзіңізге сай бір қадамнан бастаңыз. Әр ұсыныс келесі грейдіңіз талаптарына байланысты.",
        "en": "Start with one suitable step. Each recommendation connects to your next grade's requirements.",
    },
    "step_number": {"ru": "Шаг {number}", "kk": "{number}-қадам", "en": "Step {number}"},
    "factor_skill": {"ru": "Навык и цель", "kk": "Дағды және мақсат", "en": "Skill and target"},
    "factor_priority": {"ru": "Приоритет", "kk": "Маңыздылығы", "en": "Priority"},
    "factor_history": {"ru": "История участия", "kk": "Қатысу тарихы", "en": "Participation history"},
    "factor_not_critical": {
        "ru": "Входит в требования грейда",
        "kk": "Грейд талаптарына кіреді",
        "en": "Part of grade requirements",
    },
    "factor_completed": {"ru": "завершено", "kk": "аяқталды", "en": "completed"},
    "factor_avoided": {"ru": "отказов и пропусков", "kk": "бас тарту және өткізіп алу", "en": "declined or missed"},
    "factor_avoided_event": {
        "ru": "Это мероприятие уже пропускалось",
        "kk": "Бұл іс-шара бұрын өткізіліп алынған",
        "en": "This activity was previously missed",
    },
    "rationale_details": {"ru": "Полное обоснование", "kk": "Толық негіздеме", "en": "Full rationale"},
    "duration_hours": {"ru": "ч", "kk": "сағ", "en": "h"},
    "event_type_course": {"ru": "Курс", "kk": "Курс", "en": "Course"},
    "event_type_workshop": {"ru": "Практикум", "kk": "Практикум", "en": "Workshop"},
    "event_type_mentoring": {"ru": "Наставничество", "kk": "Тәлімгерлік", "en": "Mentoring"},
    "event_type_certification": {"ru": "Сертификация", "kk": "Сертификаттау", "en": "Certification"},
    "event_type_meetup": {"ru": "Встреча", "kk": "Кездесу", "en": "Meetup"},
    "event_type_onboarding": {"ru": "Адаптация", "kk": "Бейімделу", "en": "Onboarding"},
    "event_type_compliance": {"ru": "Обязательное обучение", "kk": "Міндетті оқу", "en": "Compliance"},
    "event_format_online": {"ru": "Онлайн", "kk": "Онлайн", "en": "Online"},
    "event_format_offline": {"ru": "Очно", "kk": "Офлайн", "en": "In person"},
    "event_format_self_paced": {"ru": "В своём темпе", "kk": "Өз қарқыныңызбен", "en": "Self paced"},
    "activity_details": {"ru": "Подробнее о мероприятии", "kk": "Іс-шара туралы толығырақ", "en": "About this activity"},
    "activity_description": {"ru": "Что вас ждёт", "kk": "Не күтіп тұр", "en": "What to expect"},
    "next_session": {"ru": "Ближайшая сессия", "kk": "Ең жақын сессия", "en": "Next session"},
    "session_dates": {"ru": "Доступные даты", "kk": "Қолжетімді күндер", "en": "Available dates"},
    "session_self_paced": {
        "ru": "Можно начать в своём темпе",
        "kk": "Өз қарқыныңызбен бастауға болады",
        "en": "Start at your own pace",
    },
    "session_unavailable": {
        "ru": "Новых сессий пока нет",
        "kk": "Жаңа сессиялар әзірге жоқ",
        "en": "No upcoming sessions yet",
    },
    "complete_prompt": {
        "ru": "Уже прошли активность?",
        "kk": "Іс-шарадан өтіп қойдыңыз ба?",
        "en": "Already completed this activity?",
    },
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
    "hr_intro": {
        "ru": "Ключевые сигналы развития команды — в одном месте.",
        "kk": "Команданың дамуына қатысты негізгі көрсеткіштер — бір жерде.",
        "en": "Key signals about team development in one place.",
    },
    "hr_total": {"ru": "Всего сотрудников:", "kk": "Барлық қызметкерлер:", "en": "Total employees:"},
    "hr_summary_without_step": {"ru": "Без следующего шага", "kk": "Келесі қадамсыз", "en": "Without a next step"},
    "hr_summary_risk": {"ru": "Сигнал риска", "kk": "Тәуекел белгісі", "en": "Risk signals"},
    "hr_upload_open": {"ru": "Открыть загрузку профилей", "kk": "Профильдерді жүктеуді ашу", "en": "Open profile upload"},
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
    "hr_unknown_data_title": {
        "ru": "Роль/грейд не найдены в справочнике",
        "kk": "Рөл/грейд анықтамалықтан табылмады",
        "en": "Role/grade not found in reference",
    },
    "hr_unknown_data_caption": {
        "ru": "Готовность и разрывы не посчитаны честно — не путаем это с «100% готов».",
        "kk": "Дайындық пен олқылықтар есептелмеді — мұны «100% дайын» дегенмен шатастырмаймыз.",
        "en": "Readiness and gaps could not be computed — this is not the same as \"100% ready\".",
    },
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
