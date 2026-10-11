# Проверка реализации этапа 3 — 2026-10-09

**79/79 offline tests passed**, failures/errors/skipped 0. Runtime CPython
3.13.16, SQLite 3.53.1, Linux x86_64. Run ID `20261009T175428-da56f560`, 5.865 с.
[Исходный JSON](reports/verified/stage3-offline.json) содержит per-test outcomes,
durations и SHA-256 исходников, tests/scripts, SQL, pyproject и requirements.lock.
Verifier подтвердил manifest; исходники не менялись во время прогона.

## Проверено

- Storage regression suite, включая корректировку: новые admission блокируются
  recovery gate внутри SQL transaction; уже accepted queued jobs сохраняются.
- UTF-8 bound, full-pair suffix, visible omission, oversize rejection.
- Synthetic loopback HTTP NDJSON: multibyte fragmentation, terminal record без
  newline, multi-turn messages, fixed options, safe counters и metrics.
- 3 concurrent admission / one active inference, owner-first checks,
  idempotent replay при недоступной модели.
- EOF/malformed/deadline: failed + сохранённый partial, persistent gate,
  no automatic inference retry, same-epoch recovery refusal, changed-epoch recovery.
- Post-generation model digest drift, non-finite metrics, unexpected tools,
  token/output overflow не получают completed.
- Shutdown/cancellation сохраняет attempt и освобождает lease после операций SQL.
- Legacy queued question без identity не теряется и не отправляется в inference;
  explicit retry получает современный identity snapshot.
- OS witness unit fixtures: loopback, process start epoch, wildcard rejection,
  orphan runner rejection. Реальный lsof/ps Ollama на Mac здесь не проверен.
- Live harness tested against synthetic fixture: collects all 13 observations,
  показывает omissions и **не принимает echo fixture за пройденное качество**.

Некоторые tests используют patch/fault injection и synthetic metadata/template/
engine epochs. HTTP transport и SQLite настоящие; модели Qwen в этих tests нет.
Исторические 51 stage-2 tests действительно пройдены пользователем на Darwin
arm64/Python 3.13.3/SQLite 3.49.1; исходный Mac JSON сохранён без изменений.

## Упаковка

`uv build` создал sdist/wheel v0.2.0. Wheel установлен с requirements.lock в новое
Python 3.13 virtualenv. Запуск **вне checkout** подтвердил version 0.2.0,
imports OllamaAdapter/Coordinator, packaged migration и init-db: schema 1, WAL,
FULL, FK enabled, integrity ok, 0 FK violations. Это не generation smoke test.

## Live acceptance остаётся открытой

Actual Qwen: doctor/template/tokenizer metadata, multi-turn качество, реальные
prompt_eval_count и latency, 10 sequential / 3 concurrent через service layer,
off/on/recovery на целевом Mac. Инструкции: [STAGE3.ru.md](STAGE3.ru.md).
HTTP API / LAN / мобильный интернет / browser auth / rate limit остаются следующим
этапам. CPU/RSS/swap и cold/warm benchmark — итоговой приёмке.

Не складывать reported loaded size_vram и RSS в physical RAM peak. Offline duration
выше не является метрикой скорости Qwen. Сохранённый Linux report не выдаётся за
Mac live-run; реальные observations пользователя будут отдельным новым отчётом.
