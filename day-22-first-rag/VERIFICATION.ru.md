# Day 22 — итоговая верификация

Проверка выполнена относительно `Ly41k/ai-advent-llm-api` на `main`, commit `308e3f7823bf484481de85de1e360c5348778f3e` (`Add day 21`).

## Автоматические проверки

- `python3 -m py_compile day-22-first-rag/*.py` — PASS.
- `python3 day-22-first-rag/test_day22.py -v` — **6/6 PASS**.
- `python3 day-22-first-rag/main.py questions` — возвращает **ровно 10** записей.
- Проверена коллизия имён с реальным Day 21 `evaluation.py`: Day 22 импортирует собственный `evaluation.py`, а `retrieval/storage/embeddings` берёт из Day 21.
- Все `expected_sources` существуют в текущем репозитории.
- Все `expected_terms` найдены в соответствующих README текущего `main`. В ходе проверки Day 17 gold term был исправлен с ошибочного `github__get_github_repo` на фактический `get_github_repo`.

## Сверка задания

1. `вопрос → поиск релевантных чанков → объединение с вопросом → запрос к LLM` — PASS (`answer_with_rag`).
2. Ответ без RAG — PASS (`answer_without_rag`, retrieval не вызывается).
3. Ответ с RAG — PASS (`retrieve` + `answer_question`).
4. Агент с двумя режимами — PASS (`answer(..., mode)` и CLI `--mode rag|no-rag`).
5. Сравнение одного вопроса без/с RAG — PASS (`compare`).
6. 10 контрольных вопросов — PASS (`questions.json`, строгая проверка количества).
7. Ожидание для каждого вопроса — PASS (`expectation`).
8. Ожидаемые источники — PASS (`expected_sources`).
9. Сравнение качества — PASS: оба ответа, expected-term coverage, найденные источники, source-hit rate и aggregate delta сохраняются в JSON.
10. Фиксация результата — PASS (`evaluation_results.json` создаётся командой `evaluate`).
11. Честность A/B — PASS: оба режима используют один экземпляр provider и одну generation-модель; temperature=0 задаётся Day 21 Ollama adapter.
12. Совместимость с индексом — PASS: RAG использует Day 21 `knowledge.db`; несовпадение embedding-модели отлавливается Day 21 retrieval.

## Что требует локального runtime

Реальный прогон `llama3.2`/`bge-m3` не выполнялся в среде подготовки архива, потому что здесь нет локального Ollama и построенного `knowledge.db`. Это не влияет на offline-проверку архитектуры. Для итогового runtime-прогона на вашем Mac:

```bash
source .venv/bin/activate
ollama pull bge-m3
ollama pull llama3.2
python day-21-document-indexing/main.py build   # если knowledge.db ещё нет
python day-22-first-rag/main.py compare "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
python day-22-first-rag/main.py evaluate
```

После `evaluate` открыть `day-22-first-rag/evaluation_results.json` и проверить ответы/источники по всем 10 вопросам.
