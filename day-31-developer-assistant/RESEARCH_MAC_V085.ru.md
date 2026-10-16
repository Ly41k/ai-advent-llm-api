# v085 / 0.7.15 — один отрицательный Documentation-запрос

Из корня ai-advent-llm-api, в текущем активном Python 3.13 окружении:

```bash
unzip -o ~/Downloads/day31-stage7-v085.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v085_mac.sh
```

Версия должна быть 0.7.15. unzip объединяет каталоги; не заменять scripts целиком
через Finder. Полный архив содержит 59 Python, включая все 10 проверочных скриптов,
которые ранее были потеряны при обновлении. Зависимости прежние.

Helper сначала проверяет отсутствие всех семи output files, затем запускает
native 256 tests и реальный временный FTS/Git/worker smoke без генерации,
verify существующего hybrid CURRENT (44 docs/405 chunks), bilingual admission,
GET /api/version, source/catalog guard и zero-model plan. Временный FTS smoke
не заменяет CURRENT. bge-m3 embeddings не вызываются. Новый production freeze
закрепляет текущие sources/prompt/model/index; старые freezes неприменимы.

Затем запускается только unsupported-knobs-ru через production Documentation:
максимум ОДИН Qwen call. Это диагностический запуск, не paired comparison.
Day30 и другие Ollama clients остаются выключены для выделенной сессии.
Ожидаемое корректное содержимое: unknown, claims=[]; статус completed и пустой
ответ проверяются по JSON, не объявляются PASS по одному terminal status.
Следующий запрос или пакет автоматически не запускается.

Сохранить существующие v084 reports. При stopped не удалять outputs и не повторять
helper. Здесь нет model restart/retry/cloud fallback. При закрытом gate действует
прежняя операторская prepare/restart/confirm/recovery процедура; само отклонение
завершённого model reply перезапуска не требует.

После возвращения prompt терминала прислать terminal result и семь JSON:

```text
/tmp/day31-stage7-preflight-mac-v085.json
/tmp/day31-index-verify-mac-v085.json
/tmp/day31-quality-admission-mac-v085.json
/tmp/day31-ollama-version-mac-v085.json
/tmp/day31-diagnostics-plan-mac-v085.json
/tmp/day31-diagnostics-freeze-mac-v085.json
/tmp/day31-diagnostics-unknown-ru-mac-v085.json
```

После review доступны continue_v085_mac.sh unknown/untracked/serialized и
continue_regression_v085_mac.sh receipt/assistant/dense/language/paths/main/paraphrase/uncertain.
Каждый отдельный вызов создаёт свой paired freeze и ограниченный RU/EN пакет
cap4/6, повторно полную suite не запускает. Пока их не запускать: сначала разобрать
один negative diagnostic. Изменение prompt не означает принятого исправления.

Результаты и остаток этапа 7: [CHANGES_V085.ru.md](CHANGES_V085.ru.md).
После завершения 7 сообщить Юрию и согласовать начало 8; автоматически 8 не начинать.
