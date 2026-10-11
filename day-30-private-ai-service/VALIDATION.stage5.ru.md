# Проверка этапа 5

## Принятый этап 4 на MacBook, до изменений этапа 5

Оригинальные пользовательские JSON сохранены побайтно:

- `reports/verified/http-live-20261009-223827.json`: 65/65, реальная Qwen через API,
  10 sequential multi-turn и 3 concurrent admissions, context/rate/no-auth/replay.
  13 completed, сохранено 26 сообщений; три generation queue waits
  0.004823 / 1.929282 / 0.9653 s. Генерации выполняются по одной.
- `reports/verified/http-after-restart-20261009-224326.json`: 7/7, все четыре
  истории совпали по ID/count/hash, прежний token работает, сервер ready.
- `reports/verified/https-auth-20261009-230121.json`: 14/14, verified TLS client,
  Secure/HttpOnly/Strict cookie, CSRF/Origin, session rotation/logout/revocation.
- Пользователь сообщил о прохождении operational Ollama off/on на Mac.
  Это ручное подтверждение; отдельного JSON/обрыва active generation нет.

Эти source/runtime manifests были сверены до начала этапа 5. После изменений
runtime ожидаемо другой. Исторические отчёты не переписаны; SQL schema остаётся 2.

## Этап 5 — источник и ограничения доказательств

Финальная проверка 2026-10-09: **112/112 unittest passed**, failures/errors/skipped=0,
27.229 s; **26/26 Chromium checks passed**, 24.250 s. CPython 3.13.16,
Linux x86_64, Chromium 140.0.7339.16, Playwright 1.55.0.
Source unchanged during both runs=true; offline manifest verifier=true.
Промежуточные отчёты до добавления review сохранены отдельно с суффиксом
`-before-live-review`; актуальны файлы без этого суффикса.

`reports/verified/stage5-offline.json` содержит актуальный полный source manifest
и исходы unittest. `scripts/verify_report.py` проверяет этот offline report.
`reports/verified/stage5-browser.json` — отдельный настоящий Chromium, desktop
1280×850 и mobile viewport 390/320 px, реальные TLS-сокеты и SQLite, **synthetic
inference**. См. per-check outcomes и browser/Python versions в самих JSON.

Проверяются: recent/reverse pagination и прежняя forward pagination, owner isolation,
allowlist static assets, HTTPS-only UI, CSP/no-store, реальные browser cookies/login,
persisted SSE snapshot/reload/poll fallback, lost POST response/replay без дубля,
failed generation retry, UTF-8/context/quota rejection, second browser session,
stale revision, HTML safety, revocation/logout, mobile overflow/navigation, отсутствие
browser storage, внешних запросов и uncaught JavaScript errors.

TLS: независимый httpx preflight проверяет сертификат+hostname; Chromium launch
разрешает **только SPKI-pin временного fixture certificate**, не глобальный обход
HTTPS. Это не проверка Keychain вашего обычного браузера. Browser fixture не
запускает Ollama; fake engine доступен только в tests, не в CLI/HTTP configuration.

Полный wheel проверяется отдельно: HTML/CSS/JS включены, installed runtime manifest
совпадает с checkout, корневая HTTPS-страница работает вне каталога исходников.
Backend dependencies не изменились, Playwright нужен только при browser testing.

`stage5-package.json`: wheel 0.4.0 установлен в чистый Python 3.13 venv;
23 runtime files (включая 3 UI resources) совпали с checkout. Вне исходников
HTML/JS/CSS возвращают 200/no-store. Общий размер трёх ресурсов — 37 551 байт;
это размер файлов, не измерение RAM.

`stage5-live-checker-review.json`: два контрольных сценария самого live checker
прошли на отдельном synthetic engine с реальным Chromium/TLS/SQLite. Правильные
контрольные ответы проводят весь browser flow; намеренно неправильный первый
ответ отклонён `literal_turn_0`. Это synthetic проверка harness; отдельный реальный Mac-отчёт описан ниже.
Review воспроизводится после установки optional browser requirements:

```bash
python tests/check_ui_live_harness.py --output reports/check/NEW-live-checker-review.json
```

## Реальный Web UI + Qwen на Mac — 2026-10-10

Оригинальный `reports/verified/web-ui-live-20261010-152509.json` сохранён побайтно.
**19/19 checks passed**, три completed генерации без ошибок; elapsed 20.877 s.
Darwin arm64, Python 3.13.3, Playwright 1.55.0, Chromium 140.0.7339.16.
Все 41 source SHA-256 совпали с текущими исходниками; source_unchanged=true.

Реальная Qwen2.5:14b Q4_K_M / Ollama 0.34.4, profile 8192/1024/0, margin=512.
Model digest/template совпали с предыдущей Mac-проверкой этапа 4.
Хеши трёх ответов совпали с точными controls: «принято», «мандарин», «OK».
Секретное слово сохранено в multi-turn контексте второго браузера.

Проверены reload истории, две cookie-сессии одного owner, обновление обоих
браузеров, SSE, Secure session cookie, отсутствие browser storage, внешних
запросов и JavaScript errors, очистка private view после logout.
Actual input tokens 72/108/128 <= upper bounds 662/1061/1362;
все context bounds с резервом output/margin укладываются в 8192.
TTFT: 2.410 / 0.327 / 0.338 s; engine total: 2.732 / 0.658 / 0.418 s.
Это три коротких контрольных ответа, не benchmark длинной генерации.

Обе Chromium-сессии выполнялись на Mac; mobile viewport не доказывает телефон,
LAN или mobile internet. HTTPS preflight проверил сертификат/hostname; браузер
использовал SPKI-pin указанного self-signed сертификата. Доверие Keychain обычного
Chrome/Safari, ручные UI checks, API restart во время browser generation и
physical RAM/CPU этим отчётом не подтверждены. long_a остаётся открытым.

## Ещё требуется на целевом Mac
- Обычные Chrome/Safari: вход, вопрос/уточнение, второй диалог, reload, API restart.
- Физический Android/iPhone: клавиатура, touch, safe-area, переход в фон/reconnect.
  Реальная сеть LAN/Tailscale/mobile internet — этап 6.
- Physical peak RAM/CPU/swap, final load/queue/recovery — этап 8; данные здесь
  не подтверждают расход unified memory или performance длинных ответов.
- long_a quality failure этапа 3 остаётся открытым; профиль молча не изменён.

Browser viewport/fixture не выдаются за телефон или качество Qwen. Backup operations
и перенос старой истории отложены до полной реализации по решению пользователя.
