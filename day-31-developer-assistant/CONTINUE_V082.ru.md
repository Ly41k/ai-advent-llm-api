# Продолжение этапа 7 на проверенной v0.7.12

Mac v082: 252/252 tests, 59 Python SHA совпали. Index/admission прошли.
Production RU Documentation request completed: 1081 input / 108 output tokens,
request 27.77 s; no truncation/technical failure/retry/unknown inference.
Оба claims сохраняют точный запрет даже при allowed path. Первый сформулирован
ясно, второй повторяет тот же факт фразой «Унтрекед файл контент…».
Это оставшееся замечание к wording/duplicates/usefulness, не semantic PASS всего
этапа. Raw reports и Codex review приложены; независимый human review pending.

Production/Baseline/source/schema/model/options/retrieval не меняются. Version
остаётся **0.7.12**, новый application release не нужен. Это дополнение содержит
только shell helper, инструкцию, review и copies raw JSON. Корневые README и
дни 1–30 не меняются. Existing 44/405 index retained; embeddings 0.

## Следующий короткий пакет: неизвестные параметры RU/EN

Из корня repo с активным установленным окружением:

```bash
unzip -o ~/Downloads/day31-v082-continuation.zip -d .
bash day-31-developer-assistant/scripts/continue_v082_mac.sh unknown
```

Нужно уже установленное полное v0.7.12 из day31-stage7-v082.zip.
Helper сравнит все Python SHA с приложенным native preflight, затем index verify,
план и новый **paired** freeze. Полную уже успешную suite/admission не повторяет.
Production diagnostics freeze для paired comparison не подходит.

Пакет — **2 RU/EN вопроса × Single/Multi = 4 observations**, максимум **4 Qwen
calls**, последовательно. Неизвестные имена/параметры не поддержаны цитатами:
нужен честный unknown без claims, без повторения выдуманного имени в refusal.
Rubric labels остаются вне inference. Сам helper не делает semantic PASS.
Это known regression, не held-out и не end-to-end benchmark.

Дождаться возврата prompt терминала. Прислать четыре файла:

```text
/tmp/day31-paired-unknown-mac-v082-index-verify.json
/tmp/day31-paired-unknown-mac-v082-plan.json
/tmp/day31-paired-unknown-mac-v082-freeze.json
/tmp/day31-paired-unknown-mac-v082-result.json
```

При stopped — созданные файлы и terminal output; не запускать пакет повторно.
Existing output guard срабатывает до model operations. Unknown inference
требует прежней verified recovery; ни automatic restart, ни cloud fallback нет.
Остальные Ollama clients остаются выключены. Generated calls не параллельны.

## Следующие пакеты после разбора результата

Helper поддерживает serialized (2 вопроса, 4 observations, cap 6) и untracked
(2 вопроса, 4 observations, cap 4). Они не запускаются автоматически. Каждый
создаёт собственные уникальные index-verify/plan/paired-freeze/result files с
packet name вместо unknown, под теми же fixed source/model conditions.
После первого пакета оценим точность/отказы и продолжим остальные known topics.
Ранее collected production Doc RU observation не считается парным Single/Multi.

## Что ещё требуется для этапа 7

Полная known regression под последним contract, independent held-out/human
review, три paired repeats, end-to-end и native cold/warm/RAM/swap ещё pending.
Один успешный bounded target не подтверждает стабильность всех ограничений или
качество модели вообще. Duplicate/awkward wording v082 сохраняется открытым
замечанием; staged research не предполагает новой настройки prompt после
каждого ответа. При необходимости вернёмся к нему после более широкой серии.

Этап 7 открыт. После завершения 7 сообщить Юрию и согласовать, когда начать 8.
Этап 8 автоматически не начинать.
