# Проверка JSON API

API использует ту же подписанную cookie-сессию, что и интерфейс.
Демонстрационный вход HR позволяет загружать проверочные профили жюри.

Из корня репозитория при запущенном приложении:

```bash
COOKIE_FILE=$(mktemp)
CSRF_TOKEN=$(curl -fsS -c "$COOKIE_FILE" http://localhost:8000/api/session | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])')
curl -fsS -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
  -d "employee_id=hr&password=hr-demo&csrf_token=$CSRF_TOKEN" http://localhost:8000/login
CSRF_TOKEN=$(curl -fsS -b "$COOKIE_FILE" -c "$COOKIE_FILE" http://localhost:8000/api/session | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])')
curl -fsS -b "$COOKIE_FILE" -H "X-CSRF-Token: $CSRF_TOKEN" \
  -F 'employees_file=@docs/demo/employees.json' \
  -F 'history_file=@docs/demo/activity_history.csv' http://localhost:8000/api/data/upload
curl -fsS -b "$COOKIE_FILE" http://localhost:8000/api/employees/DEMO_TRAP | python3 -m json.tool
```

Запрос ИИ-объяснения первого шага демонстрационного профиля:

```bash
curl -fsS -b "$COOKIE_FILE" -H "X-CSRF-Token: $CSRF_TOKEN" -X POST \
  'http://localhost:8000/api/employees/DEMO_TRAP/explain/EV_006?lang=ru' | python3 -m json.tool
```

Ответ содержит `text`, `facts`, `source` (`template` или `llm-agentic`) и список
`tool_calls`. Без ключа возвращается базовое объяснение. Для изменившегося или
недоступного шага сервер возвращает 409: нужно заново запросить рекомендации.

Демонстрационные логин и пароль приведены только для синтетического стенда.
Вне деморежима используйте настроенные учётные данные. После входа CSRF-токен
меняется; cookie и актуальный токен нужны для каждого изменяющего запроса.
