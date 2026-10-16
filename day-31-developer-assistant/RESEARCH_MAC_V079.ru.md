# v0.7.9 — один проверочный вызов Documentation

v078: 249 native tests passed. Второй из двух Documentation claims содержит
35 символов, 29 Latin, 0 русских букв, source e2 (EN); frame rejected. Server
Ollama 0.40.3. Raw failed report сохранён. [Разбор](CHANGES_V079.ru.md).

v079 закрывает границы claim.text: prose field не допускает ASCII quote,
backslash и line/control characters, которые старый pattern мог поглотить
вместе с JSON separators. Defect reproduced синтетически; exact Mac wording
и installed compiled grammar path не установлены. Schema + app validator
строже по формату; нет repair/translation/retry. Evidence остаются точными.
142 локальные проверки подтверждены; real v079 quality/enforcement pending.

## Запуск

Из корня repo с активным установленным окружением:

```bash
unzip -o ~/Downloads/day31-stage7-v079.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v079_mac.sh
```

Ожидается 0.7.9. **Индекс не пересобирать:** восемь project/docs и текущий
44/405 index 27519cd6caa346ac87a18639932506b5 прежние. Dependencies/OPTIONS прежние.
Helper проверяет отсутствие всех семи новых output файлов до checks/models.
Затем native suite (ожидается 251 tests), index verify, zero-model admission,
GET /api/version, production plan/freeze и один production RU request под новой schema.

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
/tmp/day31-stage7-preflight-mac-v079.json
/tmp/day31-index-verify-mac-v079.json
/tmp/day31-quality-admission-mac-v079.json
/tmp/day31-ollama-version-mac-v079.json
/tmp/day31-diagnostics-plan-mac-v079.json
/tmp/day31-diagnostics-freeze-mac-v079.json
/tmp/day31-diagnostics-untracked-ru-mac-v079.json
```

Если run снова stopped:
передать созданный отчёт и terminal error, не повторять helper. В inference_tasks
будут output_validation_reason и при claim_language output_validation_details.
claim_index — zero-based. Счётчики и evidence IDs не содержат текст модели.
Существующие reports не перезаписывать. Если отказ исчез, тоже передать отчёт:
один успешный вызов не закрывает semantic regression/enforcement acceptance.

## Дальше

Проверим требуемый русский текст и точный запрет чтения даже при allowed path,
а также отсутствие claim_language/claim_text_encoding. Затем продолжим остальные cases. EN untracked/unknown/serialized и полная known
серия ещё pending под последним contract. Этап 7 включает также независимый
held-out/human review, три paired repeats, end-to-end и native cold/warm/RAM/swap.
После завершения этапа 7 сообщить Юрию и согласовать начало этапа 8. Не начинать
этап 8 автоматически. Историческая инструкция — RESEARCH_MAC_V078.ru.md.
