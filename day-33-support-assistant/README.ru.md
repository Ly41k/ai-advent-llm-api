# День 33 — AI Support Assistant: PASS

Отдельный локальный ассистент поддержки **Bublik Private AI Service (Day 30)**:
синтетическая JSON CRM через настоящий MCP stdio и RAG по FAQ/документации.
**Course Minimum принят 17.10.2026:** Mac offline **25/25**, новая Groq
attempt-03 **HTTP 200 / полный E2E PASS**, смысл сохранённого ответа **PASS**.
[English](README.md) · [Итоговый отчёт](FINAL_REPORT.ru.md) ·
[JSON приёмки](reports/accepted.json) · [Видео в терминале](CONSOLE_VIDEO.ru.md).

## Поток и границы

Вопрос → MCP `get_ticket` → MCP `get_user` с ID только из тикета →
SQLite FTS5/BM25 top-3 → Groq JSON plan → evidence validation → ответ.
MCP SDK запускает настоящий stdio subprocess с initialize/discovery/tools calls.
Использованы подходы ClientSession/FastMCP Day 20 и bounded FTS5 Day 32;
импортов старого runtime нет, база пользователей Day 30 не открывается.

Корпус: семь FAQ RU и семь дословных EN-выдержек, всего 14 фрагментов.
README.md и API.md Day 30 читаются read-only с проверкой SHA-256 и точных цитат;
README.ru.md также изучен при подготовке FAQ. Ссылки закреплены на исходных разделах
base `c654e24610bdabed15747088f9e1691ed36d0b17`. У сохранённой ссылки
FAQ-HISTORY некорректный якорь (`#api,-persistence-and-limits`); правильная
[ссылка на раздел Day 30](https://github.com/Ly41k/ai-advent-llm-api/blob/c654e24610bdabed15747088f9e1691ed36d0b17/day-30-private-ai-service/README.md#api-persistence-and-limits).
Текст источника корректен; зафиксированные FAQ JSON и SHA приёмки не меняются.
Изменённый источник блокирует ответ.
Нет embeddings, reranker, новой векторной базы или зависимости от knowledge.db.

Модель выбирает диагноз, дословные факты документов/контекста и action IDs.
Текст действий задаёт небольшой каталог приложения. Модельные `document_facts`
не изменяются. Отдельное `application_evidence` связывает действия с найденными
подтверждениями и помечается `assigned_by: application`. Произвольная проза модели
не публикуется. Это ограниченный ассистент, не универсальная диагностика.

Принятый T-101 выполнен через curl и `openai/gpt-oss-120b`: **1370 input /
233 completion tokens**, reasoning low, temperature 0, cap 1800, один POST,
без retry/fallback. Входные источники DOC-ERRORS / FAQ-AUTH / DOC-AUTH;
итог цитирует DOC-ERRORS и FAQ-AUTH. Расчёт по прайсу $0.0003453; billing неизвестен.
Первый 403 и отказ evidence во второй попытке сохранены в итоговом отчёте.
Offline replay отделён от последующего нового live PASS.

## Установка и проверка сохранённого результата

Из корня репозитория: Python 3.12+ и SQLite FTS5; принят Mac Python 3.13.3.
Используйте отдельную среду от работающего сервиса Day 30:

```bash
python3.13 -m venv "$HOME/.venvs/bublik-day33"
source "$HOME/.venvs/bublik-day33/bin/activate"
python -m pip install -r day-33-support-assistant/requirements.txt
python day-33-support-assistant/verify_delivery.py
python -W error::ResourceWarning -m unittest discover -s day-33-support-assistant/tests -v
```

Установка зависимостей требует сети. Верификатор и все 25 тестов не вызывают
реальную модель; тесты используют настоящие локальные MCP subprocesses.
Верификатор сверяет 19 сохранённых runtime/support SHA, контекст, RAG, цитаты и
собранный ответ. Это не новый live и не новая смысловая приёмка.
`offline-linux.json` — исторические 22 теста; актуальные 25 Mac-тестов привязаны
по SHA к принятому отчёту.

## CLI и локальный HTTP

Следующие команды используют **offline_mock**, без реальной генерации:

```bash
python day-33-support-assistant/main.py answer \
  --question 'Почему не работает авторизация?'
python day-33-support-assistant/main.py answer \
  --ticket T-101 --question 'Почему не работает авторизация?'
python day-33-support-assistant/main.py prepare \
  --ticket T-101 --question 'Почему не работает авторизация?'
python day-33-support-assistant/main.py serve --port 8033
```

`prepare` выполняет настоящий MCP + RAG, без POST модели. HTTP слушает только
127.0.0.1 и всегда работает с mock. Во втором терминале:

```bash
curl --fail-with-body --max-time 10 http://127.0.0.1:8033/health
curl --fail-with-body --max-time 30 http://127.0.0.1:8033/support/answer \
  -H 'Content-Type: application/json' \
  --data '{"ticket_id":"T-101","question":"Почему не работает авторизация?"}'
```

Остановка Ctrl+C. Health проверяет liveness процесса, не готовность модели/MCP.
Настоящий Groq принят через отдельный acceptance CLI, а не через mock HTTP.
Исторические live/retry/final runners сохраняют отдельные markers. Это не команды
для видео и не разрешение новых вызовов. Их frozen README SHA предшествуют финальной
документации и теперь отличаются. Не удаляйте markers, не переписывайте исходные
отчёты и не повторяйте генерацию ради записи. Старый `main.py live` использует urllib;
принятый transport — curl. Общий adapter/live HTTP оставлен после курса.

## Обязательные сценарии и защита

| Сценарий | Проверенное поведение |
|---|---|
| T-101 | Явное истечение сессии; MCP, источники, повторный вход; real Groq PASS |
| T-102 | Другой пользователь, iPhone, отключённый Tailscale; другие действия; offline PASS |
| T-103 | Известен только HTTP 401; точная причина неизвестна; offline PASS |
| T-104 | Документации о возврате оплаты нет, правила не выдуманы; offline PASS |
| T-999 | 404 без придуманного пользователя; offline PASS |
| MCP unavailable | 503 до модели, без фиктивного успешного контекста; offline PASS |

Без тикета ответ общий. ID пользователя в вопросе не управляет CRM lookup.
Лишние поля и дубли JSON отклоняются. Лимиты: вопрос 2000 UTF-8 bytes,
HTTP body 8192 bytes. Очевидные secret patterns блокируются; ошибки не отражают
ввод/тела upstream, access logs отключены. Фильтр ограничен; используйте только
синтетические данные, не реальные credentials.

Ответ содержит ticket ID, источники/ссылки, отдельные evidence модели и приложения,
признаки использования контекста и нехватки доказательств. Дословная цитата сама
по себе не гарантирует смысл; приняты узкий каталог и явно записанный разбор.

Backlog: общий curl adapter/live HTTP, RU/EN, расширение FAQ, semantic retrieval,
общая проверка claims, настоящая CRM/авторизация оператора, постоянный MCP-процесс.
Нет Web UI, истории чата и публичного deployment. FTS5 может пропускать парафразы.
Видео уже записано владельцем с сохранённым настоящим ответом;
его [сценарий](CONSOLE_VIDEO.ru.md) доступен в репозитории. [PR #5](https://github.com/Ly41k/ai-advent-llm-api/pull/5)
объединён с `main` 17.10.2026. OpenAI API не использовался.
