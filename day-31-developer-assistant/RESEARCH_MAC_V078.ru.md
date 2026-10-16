# v0.7.8 — один диагностический вызов Documentation

v077: 246 native tests passed; RU Single untracked answered верно, RU Multi
снова rejected claim_language. Индекс/admission прошли. Schema enforcement и
причина отказа не установлены. [Разбор](CHANGES_V078.ru.md).

v078 добавляет безопасные counts-only details к прежнему отказу и фиксирует
версию действующего Ollama server. Prompt/schema, модель, evidence и решения
validator прежние. Это диагностика, semantic исправление ещё не подтверждено.
Rejected text не сохраняется и не публикуется. Никакого repair/retry/update/restart.

## Запуск

Из корня repo с активным установленным окружением:

```bash
unzip -o ~/Downloads/day31-stage7-v078.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v078_mac.sh
```

Ожидается 0.7.8. **Индекс не пересобирать:** восемь project/docs и текущий
44/405 index 27519cd6caa346ac87a18639932506b5 прежние. Dependencies/OPTIONS прежние.
Helper проверяет отсутствие всех семи новых output файлов до checks/models.
Затем native suite (ожидается 249 tests), index verify, zero-model admission,
GET /api/version, production plan/freeze и один production RU request.

**Максимум один Qwen call**, только Documentation. Single не генерируется.
Embedding calls — 0. Используется прежний known case allowed-untracked-ru из
research_quality_regression_v077.json; eval labels не входят в inference.
Это отдельный production diagnostic observation, не парный snapshot benchmark.
Новый freeze format bublik-research-freeze-v1; paired v077 freeze не использовать.

Остальные Ollama clients по-прежнему выключены. Terminal validation rejection
не требует автоматического restart. Если gate закрыт, сначала прежняя verified
recovery/prepare/confirm процедура. После unknown inference — verified recovery,
никакого silent replay. Helper сам не обновляет/перезапускает Ollama.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v078.json
/tmp/day31-index-verify-mac-v078.json
/tmp/day31-quality-admission-mac-v078.json
/tmp/day31-ollama-version-mac-v078.json
/tmp/day31-diagnostics-plan-mac-v078.json
/tmp/day31-diagnostics-freeze-mac-v078.json
/tmp/day31-diagnostics-untracked-ru-mac-v078.json
```

Если run снова stopped, это ожидаемая возможность диагностического опыта:
передать созданный отчёт и terminal error, не повторять helper. В inference_tasks
будут output_validation_reason и при claim_language output_validation_details.
claim_index — zero-based. Счётчики и evidence IDs не содержат текст модели.
Существующие reports не перезаписывать. Если отказ исчез, тоже передать отчёт:
один успешный вызов не закрывает semantic regression/enforcement acceptance.

## Дальше

По версии сервера и счётчикам уточним обработку schema/claim строк; затем явное
исправление и targeted проверка. EN untracked/unknown/serialized и полная known
серия ещё pending под последним contract. Этап 7 включает также независимый
held-out/human review, три paired repeats, end-to-end и native cold/warm/RAM/swap.
После завершения этапа 7 сообщить Юрию и согласовать начало этапа 8. Не начинать
этап 8 автоматически. Историческая инструкция — RESEARCH_MAC_V077.ru.md.
