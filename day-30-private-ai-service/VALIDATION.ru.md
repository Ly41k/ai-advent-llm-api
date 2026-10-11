# Проверка этапов 1–2 — 2026-10-09

Результат: **51/51 тестов passed**, failures 0, errors 0, skipped 0.
Это приёмка архитектуры и слоя хранения, а не готового AI-чата.

## Среда и привязка

- CPython 3.13.16, SQLite 3.53.1, Linux x86_64.
- Основа `main`: `218bc3544f114275db76906a52d38289ce8ff37b`.
- Run ID: `20261009T165527-332666a3`.
- Время: `2026-10-09T16:55:27.711123+00:00`; тестовая suite — 0.826 с.
- [JSON отчёт](reports/verified/stages-1-2.json): каждый test ID, outcome,
  duration, SHA-256 runtime/SQL/tests/scripts/pyproject.

Тестировался рабочий набор файлов поверх указанного HEAD; SHA manifest задаёт
проверенную версию точнее одного base commit. Изменений этих файлов во время
прогона нет. `verify_report.py` подтвердил соответствие manifest текущим файлам.
Длительность тестов не является latency/throughput метрикой Qwen.

## Выполнено

| Проверка | Результат |
|---|---|
| Сохранение после reopen | Те же owners, chat/message/generation IDs, порядок, тексты и receipts |
| Owner isolation | Чужие и неизвестные ресурсы одинаково недоступны; проверки cursor/send/retry/export/context |
| Durable idempotency | 10 одновременных повторов и 3 отдельных процесса дают один user message/job |
| Разные действия в одном чате | Revision/outstanding conflict предотвращает смешение двух устройств |
| Admission capacity | Per-owner/global limits проверены конкурентными SQL-транзакциями |
| Atomic rollback | Инъекция ошибки enqueue и конфликт terminal revision не оставляют частичных записей |
| Worker exclusivity | Live process и hard-link alias не создают второго worker |
| Crash recovery | Child worker реально убит; partial сохранён, interrupted виден, gate переживает restart |
| FIFO и retry | Один running для трёх чатов; retry сохраняет прежний user message и отдельные attempts |
| Deadline | Queue expiry сохраняет вопрос, включая clock с UTC+3 |
| Контекст | Только полный суффикс completed пар; история остаётся полной; foreign/orphan/duplicate IDs отвергаются |
| Supplied budget | 6656 + 1024 + 512 помещается в 8192; 6657 отвергается |
| Migrations | Repeatability/checksum, successful forward, failed forward rollback, newer/foreign schema refusal |
| Backup/restore | Настоящий SQLite backup с активным WAL; история/owners/receipts совпадают после открытия копии |
| Экспорт и ошибки | Credentials/worker token не экспортируются; SQL exceptions не раскрывают содержимое |
| CLI | Init/status/backup без HTTP, модели и cloud dependencies |

Часть rollback/race сценариев использует fault injection/patch для точного
момента сбоя. SQLite, потоки и subprocess настоящие; эти тесты не имитируют
сетевой доступ и не выдаются за такой результат.

Дополнительно `uv build` успешно создал sdist и wheel. Wheel установлен в новое
Python 3.13 virtualenv и запущен **вне checkout дня 30**. `init-db` из установленного
пакета нашёл SQL migration и вернул schema 1 / WAL / FULL / FK true / integrity ok /
0 FK violations. Сборка требует setuptools как build dependency; установленный
runtime не имеет сторонних dependencies.

## Повторить

Из каталога дня 30:

```bash
python3.13 -W error::ResourceWarning scripts/check_storage.py
python3.13 scripts/verify_report.py reports/verified/stages-1-2.json
```

Первый вызов создаёт новый файл в `reports/check/`. Сохранённый verified отчёт
не перезаписывается. После изменения исходников старый отчёт остаётся историей,
а verifier показывает несоответствие; для новой версии нужен новый прогон/отчёт.

## Не выполнено

MacBook M1/macOS, actual Qwen и tokenizer/template, HTTP/live/ready/login/CSRF,
rate limit, 10 последовательных и 3 конкурентных **HTTP+Qwen** запроса,
LAN-устройства, телефон через мобильную сеть, Ollama off/on и network isolation,
reboot/autostart, production restore. Полный список — [ACCEPTANCE](ACCEPTANCE.ru.md).

Ни mock, ни эти storage tests не подтверждают live-проверки. Реализованная
ContextPlan validation не доказывает фактический max context модели. POSIX lease
и FULL/WAL на Linux ещё не являются проверкой эксплуатационного поведения на
целевом MacBook. API/UI/network продолжатся последующими этапами.

## Последующее подтверждение на MacBook и этап 3

Исходный Linux run выше сохранён как исторический результат. Пользователь
предоставил `reports/verified/mac-stage-1-2-20261009-201916.json`: Darwin arm64,
Python 3.13.3, SQLite 3.49.1, 51/51 passed, 1.263 с. До stage-3 edits verifier
подтвердил manifest; пользователь подтвердил CLI init/reopen/backup/no-overwrite.

Stage-3 исходники изменены; старые manifests не подтверждают новую версию.
Текущие результаты и границы см. STAGE3.ru.md и `reports/verified/stage3-offline.json`.
Real Qwen/LAN/mobile в этой среде не запускались.
