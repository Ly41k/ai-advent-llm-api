# Проверка этапа 4 — 2026-10-09

## Фактический offline результат

**106/106 passed**, failures/errors/skipped=0,
27.274 s. CPython 3.13.16, SQLite 3.53.1, Linux x86_64.
Run ID `20261009T183555-6d464014`. [Исходный JSON](reports/verified/stage4-offline.json)
содержит каждый test/outcome/duration и SHA-256 source/tests/scripts/SQL/dependencies.
Source unchanged during run=true; `verify_report.py` подтвердил manifest.
Исходная миграция 001 не изменена. Новая 002 сохраняет прежние данные.

Проверено:

- Все 79 прежних storage/inference tests с обновлённой additive-migration проверкой.
- 26 ASGI HTTP/security tests: auth/CSRF/Origin, rotation/logout, owners/scopes,
  expiry/reset/revocation, сохранение только hashes credentials, pagination/OpenAPI.
- Message/retry receipts и 200 replay с выключенной synthetic моделью; 409 для
  altered payload, отсутствие duplicate user message; context overflow без записи.
- Persistent generation quota, transactional rollback, окно/restart, общий owner
  для всех credentials; 10 sequential и 3 concurrent через synthetic API.
- SSE persisted revisions/snapshots/reconnect, лимиты, revoke во время подписки,
  disconnect cleanup без отмены inference; history/replay доступны при recovery gate.
- Real TCP TLS socket: локальный сертификат действительно проверен через CA file,
  Secure cookie login, CSRF и browser HTTPS harness, приложение дважды запущено
  с одной SQLite; сохранённая synthetic история, sessions и token пережили restart.
- Реальный chunked oversized POST=413 и incomplete body=408 через TLS socket.
  Sentinel messages/password/token/cookie не попали в собранный Uvicorn log.

ASGI/protocol tests используют synthetic template/digest/epoch и fake ответы.
TLS socket test использует offline adapter и сохранённый synthetic turn.
Это **не доказательство real Qwen, LAN, мобильной сети или browser engine**.

## Mac live этапа 3 — отдельно от новых тестов

[Оригинальный Mac JSON](reports/verified/stage3-live-20261009T180550-ee1b051c.json)
сохранён byte-for-byte. Его manifest полностью совпал с исходниками перед
изменениями этапа 4 (stage-3 tree d8759bfd7436fbad3875605e5aa68cdb14ca64ed).
Darwin arm64, Python 3.13.3, SQLite 3.49.1, Ollama 0.34.4,
Qwen2.5:14b Q4_K_M. Все 13 completed, 9 harness checks=true,
observed service max active=1. Multi-turn word/correction/topic controls прошли,
full history reopen сохранил 20 сообщений, long_b явно omitted 9 старых turns.
Все actual prompt counts <= заявленной conservative границы.

**Качество long_a не прошло:** требовалось OK, ответ lantern. Actual input=1542,
bound=6613, omitted=0. Это нарушение инструкции при допустимом бюджете;
не доказательство переполнения окна. Старый harness не имел literal assertion
для long_a/long_b и показывал passed несмотря на этот пробел. Отдельный
[review JSON](reports/verified/stage3-live-review.json) фиксирует дефект;
исходный исторический отчёт не исправлялся задним числом.

Новый stage3-live-v2 harness проверяет обе длинные cases строгим сравнением
literal, а не substring. Повтор реальной Qwen с усиленными критериями ещё not_run.
Параметры модели/системный prompt не менялись; long-history quality остаётся
открытым пунктом приёмки, развитие HTTP инфраструктуры от него не зависит.

Reported loaded size/size_vram=10,269,113,711 bytes, installed=8,988,124,069 bytes.
Это engine-reported allocations/file size, **не physical RAM peak**. CPU/RSS/swap,
cold/warm и p95 с достаточным sample size — этап 8. Не складывать RSS и size_vram.

## Что ещё проверить на Mac

[STAGE4.ru.md](STAGE4.ru.md): установка dependencies, Mac offline report,
real HTTP+Qwen 10/3, API rate limit, history после рестарта API, HTTPS/cookie/CSRF
через certificate-verified клиент, отдельно operational Ollama off/on.

Новые live scripts создают exclusive new reports и synthetic chats, не пишут
API tokens/passwords/cookie/CSRF в отчёты, сверяют runtime hashes сервера с клиентом.
Hash comparison — не подпись/remote attestation. Если model/rate/quality проверка
не прошла, отчёт остаётся failed; partial observations сохраняются.

LAN/телефон/mobile browser/PWA/launchd/reboot/production restore и ресурсный
benchmark не проводились. API bind остаётся localhost; service worker/UI отсутствуют.
Инструкции сети — этап 6, GUI — 5, видео после полной реализации. Rust не внедрялся.

## Источники технических решений

- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/): ownership startup/shutdown.
- [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): session-bound CSRF + exact Origin.
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html): Argon2id t=2, m=19 MiB, p=1.
- [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html): password verification/rehash.

Эти ссылки объясняют выбор, а не подменяют результаты tests/live acceptance.
Предыдущие дни/root README и исторические JSON не изменены.


## Упаковка

Wheel/sdist 0.3.0 собраны. Wheel установлен с requirements.lock в новое
CPython 3.13.16 venv; из каталога вне checkout импортируется site-packages.
Обе SQL migrations включены, init создаёт schema 2; packaged ASGI smoke
live=200, unauthorized=401, personal token read=200, offline ready=503.
Все runtime .py/.sql wheel byte-for-byte совпали с checkout.
[Package check JSON](reports/verified/stage4-package.json). Это не Qwen smoke.


## Последующая Mac offline приёмка и исправление live checker

[Mac report](reports/verified/mac-stage4-offline-20261009T190907-71a14e3f.json):
106/106 passed, Python 3.13.3, SQLite 3.49.1, Darwin arm64, 27.334 s. Manifest
совпал полностью с исходниками до исправления checker. Оригинал не изменён.
Пользовательский console log дополнительно показывает real API live=200,
unauthorized=401, все десять sequential cases и failed после quota wait=39 s.
Сам failed http-live.json пока не предоставлен: точная причина этого run
ещё не подтверждена.

Независимо воспроизведён дефект тестового сценария: при распределённых по
времени admission Retry-After освобождает только первый слот. Старое ожидание
не гарантирует capacity для трёх новых запросов. Исправлен только checker:
wait max(61, Retry-After+1), безопасные concurrent HTTP diagnostics/failed_check.
Server quota/API/model/database schema не изменялись. 3 новых tests проверяют
старый сбой, полный flow после исправления и безопасный отчёт при чужой нагрузке.
Использованы реальная SQLite и virtual clock/synthetic HTTP, не real Qwen.
Новый offline report: reports/verified/stage4-quota-fix-offline.json.

Новый полный offline прогон: **109/109 passed**, failures/errors/skipped=0,
27.260 s, run_id `20261009T192341-d2b763b4`. Verifier подтвердил
новый manifest. Linux CPython 3.13.16/SQLite 3.53.1; новый Mac live pending.
Инструкция исправления: [QUOTA_FIX.ru.md](QUOTA_FIX.ru.md).
