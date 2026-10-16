# v0.7.5 — короткая проверка оставшихся дефектов

v074 не принята полностью: 241 native tests прошли; пять пакетов завершены,
последний stopped. EN Single unknown получил terminal ответ, отклонённый
строгим валидатором с unsupported_identifier. EN Multi не запускался.
Raw failed report сохранён. Это не overflow (5523/8192), не обрыв inference
и не повод автоматически повторять запрос. [Изменения](CHANGES_V075.ru.md).

Dense/paraphrase partial исчезли, untracked policy стала верной. Остались три
пропуска явного «не отдельная Qwen на агента» и partial у EN Multi untracked.
Общие prompt rules уточнены; новую semantic проверку ещё предстоит выполнить.
Это known regression. Независимое human/held-out acceptance остаётся pending.

## Установка и запуск

Из корня repo с активным установленным `.venv`:

```bash
unzip -o ~/Downloads/day31-stage7-v075.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v075_mac.sh
```

Ожидается 0.7.5. Архив содержит полный каталог дня 31. Индекс **не пересобирать**:
восемь project/docs прежние, существующий 44/405 index
27519cd6caa346ac87a18639932506b5 остаётся свежим. Новый freeze нужен из-за
code/prompts/catalog digest. Dependencies и model OPTIONS прежние.

Helper проверяет версию и отсутствие всех новых output файлов до работы,
затем запускает native suite (ожидается 242 tests), index verify, zero-model
FTS/admission checks, точный order plan и freeze. Далее три пакета:

| Тема RU/EN | Максимум Qwen calls |
|---|---:|
| Сериализация и отдельные копии модели | 6 |
| Untracked content при explicit allowed paths | 4 |
| Несуществующие параметры, unknown controls | 4 |

Всего 6 вопросов / 12 observations, **до 14 последовательных Qwen calls**.
Embedding calls — 0. Другие Ollama clients остаются выключенными, включая Day30.
Нет автоматического restart, frame repair или generation retry. Отклонённый
terminal reply v074 сам по себе не требует restart; если gate закрыт, сначала
прежняя explicit verified recovery/prepare/confirm процедура.

Single/Documentation используют одинаковые source rules; Main assembly прежний.
SOURCE_RULES не содержат вопросов/эталонных ответов; application validator не
повышает partial до answered. Код лишь проверяется локально с синтетическими
ответами. Реальное исправление неполноты/unknown определят native ответы.

Catalog содержит 22 уже известных вопроса. Выбраны шесть из них; их позиции и
порядок S/M/M/S не сбрасываются между пакетами. Один repeat, протокол прежний
paired-snapshot-v2. Это новый явный prompt experiment, не silent replay v074.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v075.json
/tmp/day31-index-verify-mac-v075.json
/tmp/day31-quality-admission-mac-v075.json
/tmp/day31-quality-plan-mac-v075.json
/tmp/day31-quality-freeze-mac-v075.json
/tmp/day31-quality-serialized-mac-v075.json
/tmp/day31-quality-untracked-mac-v075.json
/tmp/day31-quality-unknown-mac-v075.json
```

При остановке передать созданные отчёты и terminal error. Helper целиком повторно
не запускать: существующие outputs блокируют его до checks/model operations.
Нельзя переписывать старый failure. Technical failure останавливает следующий
пакет; semantic partial/unknown сохраняется и требует разбора.

Для ещё не выполненного пакета после установления причины остановки:

```bash
python day-31-developer-assistant/scripts/compare_single_multi.py run \
  --cases day-31-developer-assistant/evaluation/research_quality_regression_v075.json \
  --freeze /tmp/day31-quality-freeze-mac-v075.json \
  --case-id allowed-untracked-ru --case-id allowed-untracked-en \
  --repeats 1 --max-generation-calls 4 \
  --output /tmp/day31-quality-untracked-mac-v075.json
```

Этот пример применим только если untracked ещё не запускался. После uncertain
inference сначала verified recovery; повтор stopped packet требует отдельного
разбора и нового output имени. Нельзя молча получить PASS поверх failure.

## Дальше по плану

Если targeted ответы корректны, остаются 16 известных вопросов под v5,
независимые held-out и human review, три paired repeats, end-to-end и native
cold/warm/RAM/swap. Прохождение короткой серии не закрывает этап 7.
Затем этап 8 — документация/демонстрация, этап 9 — final acceptance/PR.
Предыдущая инструкция сохранена в RESEARCH_MAC_V074.ru.md.
