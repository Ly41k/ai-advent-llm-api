# v0.7.11 (архив v081) — исправление ожидаемой версии в тесте

Mac v080: preflight failed, 250/251 tests passed. Все 59 Python SHA совпали
с архивом. Тест локализации на строке 137 ожидает project-answers-v6, тогда как
v080 правильно использует project-answers-v7. Локально воспроизведён точный
AssertionError. Это пропущенное обновление теста; raw failure сохранён побайтно.
[Разбор](CHANGES_V081.ru.md). Helper остановился до real Qwen generation.

v081 меняет только expected version в существующем тесте и package version.
Production/Baseline prompts, schemas, validators, retrieval, corpus и OPTIONS
побайтно прежние относительно v080. Полный GenerationTests блок (16 tests)
прошёл локально, включая независимую JSON-schema matrix. Real v7 quality pending.

## Запуск

Из корня repo в активном установленном окружении:

```bash
unzip -o ~/Downloads/day31-stage7-v081.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v081_mac.sh
```

Ожидается **0.7.11**. Архив v081 относится к этапу 7.
Индекс 44/405 не пересобирать. Dependencies прежние. Helper проверит отсутствие
семи новых output файлов, native suite (251 tests), index verify, zero-model
admission и GET /api/version, затем новый production freeze под prompt v7.
Freeze v079/v080 не использовать: code digest/package version должны совпадать.

**Максимум один Qwen call**, только Documentation: allowed-untracked-ru из
прежнего evaluation/research_quality_regression_v077.json. Single не генерируется,
embedding calls 0. В inference не входят eval labels. Это production observation,
не парный snapshot benchmark. No warmups, hidden retries или repair.

Остальные Ollama clients выключены. Helper не обновляет/перезапускает Ollama.
Terminal application rejection не требует automatic restart. Unknown inference
требует прежней verified recovery процедуры и запрещает silent replay.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v081.json
/tmp/day31-index-verify-mac-v081.json
/tmp/day31-quality-admission-mac-v081.json
/tmp/day31-ollama-version-mac-v081.json
/tmp/day31-diagnostics-plan-mac-v081.json
/tmp/day31-diagnostics-freeze-mac-v081.json
/tmp/day31-diagnostics-untracked-ru-mac-v081.json
```

Если helper stopped, передать созданные отчёты и terminal error, не повторять.
Если completed — передать все семь файлов. Русская проза, точность запрета,
отсутствие английского оригинала/дубля проверяются по фактическому ответу;
script/schema PASS не гарантирует semantic quality. Raw failures не переписывать.

## Дальше

После clean supported RU ответа продолжим остальные known cases/оба режима.
Этап 7 открыт: full known regression, independent held-out/human review, три
paired repeats, end-to-end и native cold/warm/RAM/swap остаются pending.
После завершения 7 сообщить Юрию и согласовать, когда начинать 8.
Этап 8 автоматически не начинать. Историческая инструкция — RESEARCH_MAC_V080.ru.md.
