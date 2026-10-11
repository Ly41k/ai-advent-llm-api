# День 30 — план и границы этапов

## Требование курса

Локальная LLM как сервис на VPS или домашнем сервере, HTTP API, чат. Проверить
сетевой доступ, стабильность нескольких запросов, rate limit и max context.
Работающий сервис реализован и принят в проверенной конфигурации: runtime0.8.0,
новый Mac baseline259/259 technical/13/13 quality, история11/11, LAN/launchd6/6,
physical handoff и mobile/three-device chat подтверждены. Ограничения и deferred
задачи не скрываются: FINAL_REPORT.ru.md и ACCEPTANCE.ru.md. Этап9 оформлен11 октября2026.

## Согласованные расширения

MacBook Pro M1 / 32 GB, Python 3.13, локальная Qwen2.5:14b Q4_K_M, SQLite.
Несколько диалогов, полная сохраняемая история, продолжение с другого устройства,
адаптивный Android/iOS UI, защищённые browser sessions и API tokens, CSRF,
bounded durable queue, idempotency, восстановление после restart, backup/restore,
измерения и проверяемые отчёты. LAN-доступ должен работать без обязательного
Tailscale на каждом домашнем клиенте; внешний мобильный доступ — через Tailscale.
Cloud LLM и автоматического fallback нет. После полной реализации оформлен консольный
сценарий видео; пользователь записал UI-демонстрацию чата с нескольких устройств. Phone LAN CA отложен, основной путь — Tailscale Serve.

## Этапы

| № | Результат | Приёмка | Текущий статус |
|---:|---|---|---|
| 1 | Архитектура, API v1, состояния, лимиты и угрозы | ARCHITECTURE, API, ACCEPTANCE согласованы с уточнениями пользователя | Завершён |
| 2 | SQLite, owners, history/jobs, migrations, idempotency, revisions | Persistence, isolation, duplicate, concurrency, rollback, recovery tests | Принят на MacBook: 51/51, отчёт в reports/verified |
| 3 | Локальный async inference, ContextBuilder/token budget, queue orchestration | Реальная Qwen и multi-turn, подтверждённые model/template/local metadata | Mac: 13 completed, 9 технических checks; исторический long_a failure сохранён; v2 исправление проверено на этапе8 |
| 4 | FastAPI, login/cookies/CSRF, personal tokens, quotas/body limits, OpenAPI | API и security integration tests | Mac HTTP+Qwen 65/65, restart 7/7, HTTPS 14/14; off/on вручную |
| 5 | Responsive Web UI, history, send, SSE/polling, reconnect | Desktop/mobile browser tests | Mac Chromium UI+Qwen 19/19; fixture26/26; Android/iPhone sync/home-screen вручную подтверждены |
| 6 | LAN HTTPS и Tailscale Serve, настройки доверия/доступа | Реальные LAN устройства и телефон по мобильному интернету | Mac LAN API 20/20, tailnet API 20/20, tailnet browser+Qwen 19/19 после engine fix; Android/iPhone/Mac sync, mobile chat и Tailscale off/on вручную подтверждены; phone handoff 8/8 и after-restart 8/8, полный history hash/generation snapshot совпали; Serve status tailnet only подтверждён; пользователь подтвердил работу трёх устройств и разрешил этап 7; точная policy не прочитана checker |
| 7 | launchd, shutdown/recovery, PWA | Restart/reboot на целевом MacBook | Основной путь принят: Mac initial 6/6, restart 11/11, reboot API/HTTPS/history/new boot подтверждены; strict reboot report failed на изменении Ollama 0.34.4 → 0.40.2, Qwen/profile прежние; Android/iPhone Home Screen, sync и новый сохранённый ответ вручную подтверждены; текущий Caddy/LAN проверен6/6 на этапе8; backup отложен |
| 8 | Итоговая приёмка, качество/скорость/ресурсы | 10 sequential, 3 concurrent, отказы, сеть и все обязательные проверки | Mac baseline: technical 259/259, 16/16 completed, resources collected; quality 12/13, long_a=lantern вместо OK; три greetings без CJK; real interruption/recovery 21/21 → 9/9 → 15/15; live frozen-context ABBA: candidate26/26 против v1 24/26, long_a исправлен дважды; runtime0.8.0/private-chat-v2 установлен; upgrade30/30, новый API baseline259/259 technical/13/13 quality, 16/16 completed; offline143/143; v2 saved history11/11; LAN/launchd6/6 с новым PID32253 против27580, localhost8000 и прежней history; финальный mobile/Tailscale off-on подтверждён11 октября; saved policy audit не приложен |
| 9 | Финальные RU/EN и root README, отчёты, сценарий видео | Документы отражают проверенный runtime | Завершён: RU/EN дня/корня, final report/checklist/runbook/backlog, видео-сценарий и delivery checks; поставка опубликована в main; UI-видео записано пользователем |

Документация этапов не выдаёт future endpoints за работающий API. Корневые README
обновлены на этапе9; исходные historical JSON не изменены. Исследование Rust — после курса.
По решению пользователя operational backup/restore и перенос старой истории
выполняются после полной реализации; существующий storage backup API остаётся.

## Условия перед этапом 3

Подключить реальный Ollama adapter без копирования StructuredHTTP/V7 runtime.
Зафиксировать фактические version/digest/quantization/template; проверить бюджет
на RU/EN и длинной истории. Persistent inference gate снимается только после
проверенного idle/restart, не по одному `/api/ps`, который показывает загрузку,
а не доказательство отсутствия вычисления. Выбран operational recovery по OS listener epoch + проверке отсутствия orphan
Ollama runners; не перезапускать общий Ollama скрытно поверх Revik/других уроков.

Параметры 8192/1024/0 стартовые. После замеров разрешено обоснованно изменить их
в новом серверном профиле; прежние job snapshots и отчёты сохраняются.
