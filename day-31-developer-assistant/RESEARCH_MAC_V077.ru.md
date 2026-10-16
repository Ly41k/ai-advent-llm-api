# v0.7.7 — короткая проверка новой схемы на одном RU вопросе

v076: 242 native tests, index verify и admission passed. RU Single untracked
answered верно. RU Multi отклонён с claim_language, остальные темы не запускались.
Всего две observations / два Qwen calls. Failed report сохранён.
[Разбор и изменение](CHANGES_V077.ru.md).

v077 переносит прежний символьный language check также в JSON Schema claim.text.
Prompts, evidence и строгий validator приложения прежние. Новый pattern на
установленной Ollama ещё не измерен; unit fixtures не подтверждают его enforcement.
Приложение не переводит/исправляет/retries model output. Качество смысла и полноты
проверяется отдельно. Этап 7 открыт; 8 только после завершения 7 и согласования.

## Установка

Из корня repo с активным установленным окружением:

```bash
unzip -o ~/Downloads/day31-stage7-v077.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v077_mac.sh
```

Ожидается 0.7.7. **Индекс не пересобирать:** восемь project/docs прежние,
существующий 44/405 index 27519cd6caa346ac87a18639932506b5 остаётся свежим.
Dependencies/model profile/OPTIONS прежние. Новый freeze нужен из-за schema/code
и выбранного catalog digest. Перед первым действием helper проверяет новые outputs.

Helper: native suite (ожидается 246 tests, включая независимый jsonschema matrix),
index verify, zero-model FTS/admission, точный plan и freeze. Затем только:

| Вопрос | Режимы | Максимум Qwen calls |
|---|---|---:|
| Untracked RU при explicit allowed paths | Single → Multi | 2 |

Один known вопрос, две observations, один repeat. Порядок задан прежней frozen
catalog position 20. Ни embeddings, ни последующие пакеты helper не запускает.
Все model operations последовательны; другие Ollama clients, включая Day30,
остаются выключенными. Автоматического restart/cloud fallback/replay нет.
Отклонённый terminal reply v076 сам по себе не требует restart; если gate закрыт,
сначала прежняя verified recovery/prepare/confirm процедура.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v077.json
/tmp/day31-index-verify-mac-v077.json
/tmp/day31-quality-admission-mac-v077.json
/tmp/day31-quality-plan-mac-v077.json
/tmp/day31-quality-freeze-mac-v077.json
/tmp/day31-quality-untracked-ru-mac-v077.json
```

При остановке передать созданные отчёты и terminal error. Helper целиком повторно
не запускать: существующие outputs блокируют повтор до checks/model operations.
Technical failure сохраняется; валидный partial/unknown также требует разбора,
не означает semantic PASS. Unknown inference требует verified recovery, не тихого
повтора. Нельзя переписывать failed report или старый frame в успешный.

После проверки этой пары отдельно продолжим EN untracked, unknown и serialized
под тем же новым freeze, сохраняя outputs в свежие файлы. Первое чтение отчётов
должно подтвердить одновременно отсутствие технического сбоя, требуемый язык,
точный запрет чтения и explicit allowed-path условие. Для unknown нельзя считать
generic memory facts подтверждением отсутствующего механизма/его параметров.
Проверка одного вопроса не закрывает всю регрессию и не доказывает независимое качество.

## Завершение этапа 7

Нужны полная revised-contract known regression, независимые held-out/human checks,
три paired repeats, end-to-end и native cold/warm/RAM/swap. Когда все критерии
этапа 7 выполнены, явно сообщить Юрию и согласовать время начала этапа 8.
Не начинать этап 8 автоматически. Историческая инструкция — RESEARCH_MAC_V076.ru.md.
