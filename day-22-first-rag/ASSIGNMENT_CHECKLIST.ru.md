# Day 22 — проверка задания

| Требование | Реализация | Проверка |
|---|---|---|
| Вопрос → поиск релевантных чанков | `Day22RAGAgent.answer_with_rag()` вызывает Day 21 `retrieve()` | `test_rag_is_question_search_context_llm` |
| Объединение чанков с вопросом → LLM | Day 21 `answer_question()` получает исходный вопрос и retrieved `Hit[]` | тот же тест проверяет prompt |
| Ответ без RAG | `answer_without_rag()` не обращается к embedding/index | `test_no_rag_does_not_touch_retrieval` |
| Ответ с RAG | `answer_with_rag()` | offline test + `main.py ask --mode rag` |
| Два режима агента | `answer(..., mode)` / CLI `--mode` | тесты + CLI |
| Сравнение одного вопроса | `compare()` | `test_compare_uses_both_modes_for_same_question` |
| 10 контрольных вопросов | `questions.json` | `load_questions()` требует ровно 10 |
| Ожидание для каждого | `expectation` | validation в `load_questions()` |
| Ожидаемые источники | `expected_sources` | validation + evaluation report |
| Сравнение качества | term coverage, source hit, aggregate delta | `evaluate_questions()` |
| Фиксация результата | `evaluation_results.json` | `main.py evaluate` |
| Одинаковая LLM для A/B | один `provider` внутри одного агента | архитектура `Day22RAGAgent` |
