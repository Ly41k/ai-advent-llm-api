# v0.7.10 (архив v080) — русский ответ без английского дубля

Mac v079: 251/251 tests, 59 Python SHA совпали с архивом. Index verify и
zero-model admission прошли. Один Documentation call completed: claim_language
и claim_text_encoding отсутствуют. Первый claim правильно запрещает чтение
untracked-файла даже при allowed path; второй содержит EN фразу и RU перевод.
Это технический PASS, но requested-language quality ещё не принята.
Raw отчёты сохранены побайтно; [разбор](CHANGES_V080.ru.md).

v080 уточняет общее RU/EN правило Single и Multi: перевести прозаическое
содержание источника, не добавлять оригинал или дубль; подтверждённые API имена
сохранять. Schema/application validator прежние; script check не language detector.
21 affected checks прошли локально, 40 public inputs без truncation укладываются
в 8192 (max 8182). Реальный результат нового prompt ещё не измерен.

## Запуск

Из корня repo с активным установленным окружением:

```bash
unzip -o ~/Downloads/day31-stage7-v080.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v080_mac.sh
```

Версия — **0.7.10**, не 0.8.0: продолжаем этап 7.
Индекс 44 docs / 405 chunks не пересобирать. Project/docs, corpus, retrieval,
OPTIONS и dependencies прежние. Helper проверит отсутствие всех семи новых
output файлов, suite (251 tests), index verify, zero-model admission, GET
/api/version, затем создаст новый production freeze под prompt v7.

**Максимум один Qwen call**, только Documentation, known allowed-untracked-ru.
Single не генерируется, embedding calls 0. Case catalog v077 прежний побайтно;
eval labels не входят в inference. Это production observation, не paired benchmark.
Старый v079 freeze не использовать: prompt изменён. Helper не обновляет и не
перезапускает Ollama. Остальные клиенты Ollama по-прежнему выключены.
Terminal application rejection не требует automatic restart; unknown inference
требует прежней verified recovery процедуры и запрещает silent replay.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v080.json
/tmp/day31-index-verify-mac-v080.json
/tmp/day31-quality-admission-mac-v080.json
/tmp/day31-ollama-version-mac-v080.json
/tmp/day31-diagnostics-plan-mac-v080.json
/tmp/day31-diagnostics-freeze-mac-v080.json
/tmp/day31-diagnostics-untracked-ru-mac-v080.json
```

При остановке передать созданные отчёты и terminal error; не повторять helper.
Raw failures/partial не исправлять поверх PASS. При completed также передать
все семь файлов: отсутствие структурной ошибки не подтверждает русский язык,
точность и полноту ответа автоматически.

## Дальше

После чистого supported RU ответа продолжим остальные known cases/оба режима.
Один вызов не доказывает стабильность и не закрывает semantic acceptance.
Этап 7 открыт: независимые held-out/human review, три paired repeats, end-to-end
и native cold/warm/RAM/swap остаются pending. После завершения 7 сообщить Юрию
и согласовать, когда начинать 8. Этап 8 автоматически не начинать.
Историческая инструкция — RESEARCH_MAC_V079.ru.md.
