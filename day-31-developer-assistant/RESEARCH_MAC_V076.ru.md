# v0.7.6 — короткая проверка оставшихся дефектов

v075: 242 native tests, index verify и admission прошли. Serialized завершён;
untracked stopped после RU Single с claim_language. 5/12 observations,
7 Qwen calls. Unknown пакет и остальные untracked modes не запускались.
Raw failure сохранён. Budget отклонённого входа 7044/8192; terminal reply
завершён, rejected text не retained. [Разбор](CHANGES_V076.ru.md).

RU Single явно отвергает отдельные копии Qwen; остальные три ответа пропускают
эту часть. Native v076 должен проверить новые общие per-claim language и
both-alternatives rules. Нет автоматического перевода/retry/frame repair.
Этап 7 открыт; этап 8 только после завершения 7 и согласования с Юрием.

## Установка и запуск

Из корня repo с активным установленным `.venv`:

```bash
unzip -o ~/Downloads/day31-stage7-v076.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v076_mac.sh
```

Ожидается 0.7.6. Архив содержит полный каталог дня 31. Индекс **не пересобирать**:
восемь project/docs прежние, существующий 44/405 index
27519cd6caa346ac87a18639932506b5 остаётся свежим. Новый freeze нужен из-за
code/prompts/catalog digest. Dependencies и model OPTIONS прежние.

Helper проверяет версию и отсутствие всех новых output файлов до работы,
затем запускает native suite (ожидается 242 tests), index verify, zero-model
FTS/admission checks, точный order plan и freeze. Далее три пакета:

| Тема RU/EN | Максимум Qwen calls |
|---|---:|
| Untracked content при explicit allowed paths | 4 |
| Несуществующие параметры, unknown controls | 4 |
| Сериализация и отдельные копии модели | 6 |

Всего 6 вопросов / 12 observations, **до 14 последовательных Qwen calls**.
Embedding calls — 0. Другие Ollama clients остаются выключенными, включая Day30.
Нет автоматического restart, frame repair или generation retry. Отклонённый
terminal reply v075 сам по себе не требует restart; если gate закрыт, сначала
прежняя explicit verified recovery/prepare/confirm процедура.

Single/Documentation используют одинаковые source rules; Main assembly прежний.
Каждый claim.text должен быть на языке RU/EN prompt, независимо от языка цитаты.
В сравнении явно назвать оба варианта по источнику. SOURCE_RULES не содержат вопросов/эталонных ответов; application validator не
повышает partial до answered. Код лишь проверяется локально с синтетическими
ответами. Реальное исправление неполноты/unknown определят native ответы.

Catalog содержит 22 уже известных вопроса. Выбраны шесть из них; их позиции и
порядок S/M/M/S не сбрасываются между пакетами. Один repeat, протокол прежний
paired-snapshot-v2. Untracked проверяется первым. Это явный новый prompt experiment, не silent replay v075.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v076.json
/tmp/day31-index-verify-mac-v076.json
/tmp/day31-quality-admission-mac-v076.json
/tmp/day31-quality-plan-mac-v076.json
/tmp/day31-quality-freeze-mac-v076.json
/tmp/day31-quality-untracked-mac-v076.json
/tmp/day31-quality-unknown-mac-v076.json
/tmp/day31-quality-serialized-mac-v076.json
```

При остановке передать созданные отчёты и terminal error. Helper целиком повторно
не запускать: существующие outputs блокируют его до checks/model operations.
Нельзя переписывать старый failure. Technical failure останавливает следующий
пакет; semantic partial/unknown сохраняется и требует разбора.

Для ещё не выполненного пакета после установления причины остановки:

```bash
python day-31-developer-assistant/scripts/compare_single_multi.py run \
  --cases day-31-developer-assistant/evaluation/research_quality_regression_v076.json \
  --freeze /tmp/day31-quality-freeze-mac-v076.json \
  --case-id allowed-untracked-ru --case-id allowed-untracked-en \
  --repeats 1 --max-generation-calls 4 \
  --output /tmp/day31-quality-untracked-mac-v076.json
```

Этот пример применим только если untracked ещё не запускался. После uncertain
inference сначала verified recovery; повтор stopped packet требует отдельного
разбора и нового output имени. Нельзя молча получить PASS поверх failure.

## Дальше по плану

Если targeted ответы корректны, остаются 16 известных вопросов под v6,
независимые held-out и human review, три paired repeats, end-to-end и native
cold/warm/RAM/swap. Прохождение короткой серии не закрывает этап 7.
После завершения этапа 7 явно сообщить Юрию и согласовать начало этапа 8.
Этап 8 — документация/демонстрация, этап 9 — final acceptance/PR.
Не начинать этап 8 автоматически. Историческая инструкция — RESEARCH_MAC_V075.ru.md.
