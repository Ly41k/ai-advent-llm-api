# v0.7.3 — двуязычный корпус и проверка качества

Диагностика Mac v072: 20/20 source selections совпали с исходными снимками;
code/corpus/index/Git conditions сохранились, model HTTP/embedding calls — 0.
Main RU: английские архитектурные чанки были на 48-м и 136-м местах;
точный контракт checked claims — в чанке на 136-м месте. Path-limit RU: нужный
английский раздел не совпал с FTS-запросом. Dense RU Single получил нужную
выдержку, но отказался отвечать — это отдельная проблема генерации.
[Изменение и ограничения](CHANGES_V073.ru.md).

## Установка и запуск

Из корня ai-advent-llm-api с активным `.venv`:

```bash
unzip -o ~/Downloads/day31-stage7-v073.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v073_mac.sh
```

Ожидается версия 0.7.3. Архив содержит полную папку дня 31. Dependencies прежние.
Native suite ожидается 236 tests; локально прошли 125 affected checks на
Python 3.12.14. Полный native suite использует установленное Mac окружение
Python 3.13 с MCP/jsonschema. Root README и другие дни не меняются.

## Шаги helper

1. Native stage7 tests и actual-project FTS/Git/owned-worker smoke без `--live`.
2. Read-only `models status`. Закрытый gate останавливает работу до build/inference.
3. Новый `index build --mode hybrid`, затем `index verify`.
4. 20 production-budget FTS searches и 12 прежних calibration вопросов без
   моделей: шесть target source/keyword hits; все непустые Single/Documentation
   inputs в бюджете; 10 positive hits@5 и 2 пустых negatives; стабильные conditions.
5. Новый freeze для known-regression catalog v073. Только metadata checks,
   без generation и query embeddings.
6. Три пакета: Main RU/EN, path-limit RU/EN, dense-private RU/EN. Каждый содержит
   два вопроса, четыре Single/Multi observations, максимум шесть Qwen calls.
   Затем два прежних unknown controls RU/EN: четыре observations, максимум
   четыре Qwen calls.

Верхняя граница — 8 вопросов, 16 ответов и **22 Qwen generations**, последовательно.
Отдельно считаются bge-m3 calls при rebuild всех чанков. Documents/chunks,
embedding calls и время сборки фиксирует build report. На прежнем Mac repository
ожидаются 44 документа: добавлены ровно четыре явных RU sources. Число чанков
заранее не объявляется измеренным.

Day30/Revik/прочие клиенты Ollama должны быть остановлены по прежним правилам
выделенной сессии. Helper не перезапускает Ollama и не повторяет dispatch.
При закрытом gate нужна существующая prepare → operator restart → confirm
процедура из RAG_MAC.ru.md. Старый индекс сохраняется; rebuild публикует новый
CURRENT атомарно. Старый v072 freeze не подходит.

Helper останавливается на первой technical/retrieval/admission failure.
Semantic unknown/partial сохраняются для разбора, не исправляются в PASS.
Existing output не перезаписывается: все имена проверяются до первого шага,
Bash noclobber дополнительно защищает CLI outputs.

## Отчёты для чата

```text
/tmp/day31-stage7-preflight-mac-v073.json
/tmp/day31-models-status-mac-v073.json
/tmp/day31-index-build-mac-v073.json
/tmp/day31-index-verify-mac-v073.json
/tmp/day31-bilingual-retrieval-mac-v073.json
/tmp/day31-bilingual-freeze-mac-v073.json
/tmp/day31-bilingual-main-mac-v073.json
/tmp/day31-bilingual-path-mac-v073.json
/tmp/day31-bilingual-dense-mac-v073.json
/tmp/day31-bilingual-unknown-mac-v073.json
```

Если helper остановился, прислать созданные отчёты и terminal error. Не запускать
его целиком повторно. Уже успешные generation пакеты не повторять.

## Продолжение с ещё не выполненного шага

После устранения конкретной причины — только следующий шаг. Остановленный пакет
получает новый output filename; исходная failure остаётся. При uncertain dispatch
сначала explicit verified recovery.

```bash
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage7.py --output /tmp/day31-stage7-preflight-mac-v073.json
python day-31-developer-assistant/main.py models status
python day-31-developer-assistant/main.py index build --mode hybrid
python day-31-developer-assistant/main.py index verify
python day-31-developer-assistant/scripts/check_bilingual_retrieval.py --output /tmp/day31-bilingual-retrieval-mac-v073.json
python day-31-developer-assistant/scripts/compare_single_multi.py freeze --cases day-31-developer-assistant/evaluation/research_bilingual_regression_v073.json --output /tmp/day31-bilingual-freeze-mac-v073.json
```

Для ещё не запущенного Main пакета (остальные IDs — в helper):

```bash
python day-31-developer-assistant/scripts/compare_single_multi.py run \
  --cases day-31-developer-assistant/evaluation/research_bilingual_regression_v073.json \
  --freeze /tmp/day31-bilingual-freeze-mac-v073.json \
  --case-id main-authority-branch-ru --case-id main-authority-branch-en \
  --repeats 1 --max-generation-calls 6 \
  --output /tmp/day31-bilingual-main-mac-v073.json
```

Это known regression, не held-out. Изменение корпуса не гарантирует исправления
Qwen unknown/partial. Semantic review новых ответов, dense/hybrid comparison на
новом корпусе, полный regression, human review, counterbalance трёх repeats,
end-to-end и cold/warm/RAM/swap остаются этапом 7.
Историческая инструкция v072 — RESEARCH_MAC_V072.ru.md.
