# Этапы 1–2: проверка на Mac

Это действия оператора на своём Mac. Пакет не останавливает сервисы автоматически.
База/история/настройки дня 30 не изменяются. Для текущих Git tests модель не нужна;
выключение day30 готовит отдельную сессию будущих inference этапов.

## 1. Штатно выключить day30

Прекрати новые запросы и дождись завершения текущего ответа. Если использовался
ручной `serve`, останови его Ctrl+C в том терминале. Для установленного launchd:

```bash
launchctl disable "gui/$(id -u)/local.bublik.private-ai.api"
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
```

`disable` предотвращает новый автозапуск, `bootout` выгружает job. Пустой lsof
подтверждает отсутствие listener на этом порту; один `disable` ещё не останавливает
работающий job. Если bootout сообщает об отсутствующем job, проверяй doctor;
ошибку доступа не считать успешной остановкой. Caddy/Tailscale не запускают inference
самостоятельно и не требуют изменения конфигурации.

Установи пакет в отдельную venv по README, затем **из корня репозитория**:

```bash
python day-31-developer-assistant/main.py doctor
```

Ожидается `status=passed`, `mac_check=true`, `day30_off=true`.
Если LaunchAgent plist установлен, guard также требует disabled override.
Непонятный ответ launchctl или невозможность проверить процессы дают
`day30_isolation_unverified`, а найденный сервис/listener — `day30_service_active`.
Не считать эту ошибку разрешением продолжить inference.

Если day30 был запущен на дополнительном порту, добавь его к проверке:

```bash
python day-31-developer-assistant/main.py doctor --day30-port 8001
```

8000 проверяется всегда; аргумент только добавляет порты. Guard знает штатные
`bublik_service`/uvicorn launchers и paths дня 30. Произвольный wrapper с другим
именем/import не получает гарантии обнаружения. Работать через известный launcher.

`ollama_idle_verified=false` — ожидаемый честный результат: проверка day30 не
доказывает остановку старой генерации. Если API был остановлен посреди ответа,
перед будущим inference понадобится отдельное проверяемое восстановление Ollama.
Новый пакет пока вообще не отправляет запросы модели.

## 2. Проверить настоящий MCP

```bash
python day-31-developer-assistant/main.py --root "$PWD" git branch
python day-31-developer-assistant/main.py --root "$PWD" git status
python day-31-developer-assistant/main.py --root "$PWD" git files
python day-31-developer-assistant/main.py --root "$PWD" git diff
```

В branch ожидается действительная локальная ветка; она может отличаться от
`main`. `transport=mcp_stdio`, discovery содержит 4 tools, `llm_calls=0`.
Если новая папка ещё не добавлена в Git, status покажет её файлы untracked,
а обычный diff не покажет untracked content. Это нормальное поведение.
Не нужно делать commit или менять текущую ветку ради демонстрации.

## 3. Получить отчёт тестов

```bash
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage12.py \
  --output /tmp/day31-stage12-mac.json
```

Expected для 0.1.2: 40 tests, status passed, platform Darwin. Тесты создают и изменяют
только temporary fixture repos; новый production Git tool остаётся read-only.
`launchctl` branches в suite моделируются и не подтверждают выключение сервиса:
это подтверждает отдельный настоящий doctor выше.

После этих проверок готовы перейти к Project RAG. Реальные bge-m3/Qwen проверки,
субагенты и single/multi benchmark будут отдельными отчётами.

## Возвращение к day30 после отдельной сессии

Не выполнять во время будущих day31 inference экспериментов. После завершения
отдельной сессии можно восстановить исходный LaunchAgent:

```bash
launchctl enable "gui/$(id -u)/local.bublik.private-ai.api"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Это тот же установленный job и прежняя база. Пакет не удаляет plist и не создаёт
второй экземпляр сервиса.
