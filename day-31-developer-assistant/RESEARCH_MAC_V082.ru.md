# v0.7.12 (архив v082) — конечная длина claim.text в pattern

Mac v081: 251 tests passed, 59 Python SHA совпали. Final run остановлен:
output_truncated, 1 completed Qwen call, 1081 input / 1024 output tokens.
Незавершённый frame отклонён, claims не опубликованы; unknown inference 0.
Начальный running checkpoint и окончательный stopped report сохранены отдельно.
[Разбор](CHANGES_V082.ru.md). Точная raw формулировка модели не retained.

v082 задаёт диапазон 1–600 прямо в regex, вместо unbounded repetitions.
RU claim начинается русской буквой; API можно указать после первого слова,
например «Инструмент git_diff ...». EN исключает русские буквы, как раньше.
Quote/backslash/line controls прежним образом запрещены только в claims.
Оригинальные source excerpts/цитаты не меняются. Schema и app validator
согласованы; нет text cleanup, translation repair, retry или увеличения tokens.
Prompt v7/OPTIONS прежние. 143 local tests passed; native ожидается 252.

## Запуск

Из корня repo в активном установленном окружении:

```bash
unzip -o ~/Downloads/day31-stage7-v082.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v082_mac.sh
```

Ожидается **0.7.12**. Индекс 44/405 не пересобирать. Dependencies прежние.
Helper проверит отсутствие новых output файлов, suite (252 tests), index verify,
zero-model admission, GET /api/version, создаст новый freeze под schema v4.
Старый v081 freeze не использовать: schema/source digests изменены.

**Максимум один Qwen call**, production Documentation, allowed-untracked-ru.
Single не генерируется; embedding calls 0. Известный v077 catalog прежний побайтно;
labels не входят в inference. Это explicit schema experiment, не silent replay
и не paired comparison. Helper не обновляет/перезапускает Ollama.
Остальные Ollama clients выключены. Completed validation rejection не требует
automatic restart. При unknown inference — прежняя verified recovery, no replay.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v082.json
/tmp/day31-index-verify-mac-v082.json
/tmp/day31-quality-admission-mac-v082.json
/tmp/day31-ollama-version-mac-v082.json
/tmp/day31-diagnostics-plan-mac-v082.json
/tmp/day31-diagnostics-freeze-mac-v082.json
/tmp/day31-diagnostics-untracked-ru-mac-v082.json
```

Дождаться завершения helper и возврата prompt терминала, затем прикрепить файлы.
Промежуточный status running не содержит final result. При stopped передать
финальный JSON и terminal error; не повторять helper. Существующие reports
не overwrite. Если validation passed, проверим язык/точность/полноту вручную.

## Границы и дальше

600 символов на claim не гарантируют, что весь ответ уложится в 1024 tokens.
Точный источник разрастания v081 (строка, повтор claims, whitespace) неизвестен.
Новый regex закрывает обнаруженный дефект, но его эффект на Qwen ещё не измерен.
Russian-letter start и script exclusion не являются language/semantic detector.
Этап 7 открыт: остальные known cases/оба режима, независимый held-out/human
review, три paired repeats, end-to-end и native cold/warm/RAM/swap pending.
После завершения 7 сообщить Юрию и согласовать, когда начать 8. Автоматически
этап 8 не начинать. Историческая инструкция — RESEARCH_MAC_V081.ru.md.
