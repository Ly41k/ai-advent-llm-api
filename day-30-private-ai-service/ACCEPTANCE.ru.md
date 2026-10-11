# День 30 — итоговая матрица приёмки

Состояние11 октября2026: работающий приватный сервис принят в проверенной
конфигурации, этап9 оформляет документацию и доставку. `not_run`/deferred не являются
PASS. Synthetic inference, Mac→свойLANIP и viewport не доказывают реальный телефон.
Ссылки на исходные JSON и ограничения: [FINAL_REPORT.ru.md](FINAL_REPORT.ru.md).

## Обязательное задание курса

| Требование | Критерий | Результат |
|---|---|---|
| Домашний сервер и локальная LLM | Qwen вызывается локально, без cloud fallback | MacBook M1/Ollama/Qwen2.5:14b Q4_K_M; фактические digest/template/version |
| HTTP API и чат | Authenticated API v1 + Web UI | Реализовано, FastAPI и documented OpenAPI |
| Сетевой доступ | Реальный клиент другого устройства | Physical Android handoff8/8; Android/iPhone/Mac sync вручную |
| Мобильная сеть | Wi-Fi выключен на телефоне, Tailscale включён, ответ сохранён | Пользователь подтвердил mobile chat и повторный off/on11 октября |
| 10 последовательных | Все completed, историю/ответы не теряем | V2 baseline10/10; quality controls13/13 |
| 3 конкурентных | Три HTTP admission, безопасная очередь, независимые ответы | Три202/completed, queue max2, inference max1 |
| Rate limit | 429/Retry-After, отказ без новой inference/истории | V2 HTTP120/min; generation10/min — earlier Mac + текущий transactional suite |
| Max context | Bound≤budget, omission видна, oversize не сохраняется | Upper bound≤6656, long_b omitted9, overflow422; исходная v1 quality error исправлена проверенным v2 |

## Согласованные расширения

| Требование | Критерий | Результат |
|---|---|---|
| Несколько чатов и owners | Разделённые ресурсы и контекст | SQLite/HTTP/SSE isolation tests; foreign IDs404 |
| Полная история и cross-device continuity | Тот же owner/chat ID, прежние данные | Три устройства вручную; physical handoff8/8 и after-restart8/8 |
| История после restart/upgrade | Stable IDs/content/order/status/profile snapshots | Upgrade30/30; v2 seven chats/32 messages11/11; новый API PID подтверждён LAN6/6 |
| Авторизация/CSRF/TLS | 401, cookie flags, Origin/CSRF, scoped tokens | Real TLS/Chromium + ASGI regression, no browser token storage |
| Body/output/queue caps | Reject before write, одна активная генерация | 32KiB/16KiB/1024tokens, durable quotas/capacity |
| Durable retries | Один logical request, stable receipt, partial/status | Real API replay + threads/processes/SQLite race tests |
| Недоступная модель | live/history доступны, new inference503, restore | Mac operational off/on вручную, cached readiness≤5s |
| Прерванный stream | Partial сохранён, terminal/gate, verified epoch, no old replay | Real v1 chain21/21→9/9→15/15; 707chars, новый explicit запрос completed |
| Ollama localhost | Listener loopback, API-only routing | OS witnesses + refused Mac LAN/tailnet port probes; independent remote scan not_run |
| LAN без обязательного Tailscale | Caddy TLS с доверенным собственным CA | Mac LAN20/20 и текущий LAN6/6; phone CA/precise direct-LAN phone conditions deferred |
| PWA / restart login | Home screen и saved answer/reopen | Android/iPhone вручную, synthetic Chromium/PWA11/11 |
| Автозапуск | LaunchAgent и новый PID/history | Mac initial6/6/restart11/11; strict reboot failed engine-version identity; actual new boot/history/manual chat подтверждены |
| Приватность логов | Нет content/secrets по умолчанию | Sentinel regressions; Mac launchd stdout/stderr=/dev/null; diagnostics limited |
| Измерения | Версии/identity/sample sizes/raw counters сохранены | V2 resources106samples, metrics в final report; no RSS+VRAM sum |

## Реализация и документация

- [x] Код и конфигурация в `day-30-private-ai-service/`, предыдущие runtime не изменены.
- [x] Текущий offline143/143, Chromium26/26, PWA11/11, clean wheel10/10.
- [x] README.md/README.ru.md дня30 и корня; API, architecture, Mac/phone runbook.
- [x] Отдельный final report, сохранённые original passed/failed JSON и source hashes.
- [x] Backlog: Rust после курса, backup/restore и другие улучшения.
- [x] Консольный сценарий видео с запуском, реальным API и новым report directory.
- [x] Пользователь записал UI-видео с сообщениями с телефонов.
- [x] Код опубликован пользователем в main: `d6c651c75d8f44c99f4780a3dffb9f1c8c5ef348`.
  Само видео здесь не анализировалось; факт записи подтверждён пользователем.

## Явно отложено / не доказано

- Operational production restore/retention/off-host backup и перенос старого owner.
- Независимая проверка сохранённых tailnet grants/ACLs и policy tests; ранее показан
  tailnet-only Serve, текущий off/on подтверждён вручную, fresh CLI snapshot не приложен.
- Телефонные LAN CA настройки и independent physical remote port scan.
- Forced API SIGKILL, soak/GPU/physical footprint, полный OS/browser/logout matrix.

Этот список не создаёт скрытой гарантии полной security certification или защиты
от отказа диска. До переноса важных данных operational backup/restore остаётся
отдельной практической задачей. Agents/RAG/voice и Rust не
реализуются в дне30.

## Повторная проверка

Saved offline report: `python scripts/verify_report.py reports/verified/stage8-prompt-v2-offline.json`.
Новые runs используют scripts/check_storage.py и реальные acceptance/browser/network
checkers. Все output paths новые; старые JSON не переписывать. Historical source guard
может закономерно не совпасть с текущим runtime — это не повод менять original report.
Обычный history check требует same-source baseline; explicit v1→v2 upgrade проверяется
отдельным read-only checker. См. [CONSOLE_VIDEO.ru.md](CONSOLE_VIDEO.ru.md).
