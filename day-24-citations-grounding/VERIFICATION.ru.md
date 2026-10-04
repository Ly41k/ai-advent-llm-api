# Итоговая проверка Дня24 — v14 diagnostic

**Подтверждено:**10/10 positive answers с valid sources/quotes и manually sufficient meaning;2/2 negative отказа. Один полный пользовательский Ollama прогон v14 diagnostic, без смешивания разных версий. User environment: MacM1/32GB/Python3.13.3, bge-m3/qwen2.5:14b. Локальные code tests: Python3.12.14,150 tests (116+7+6+21). Own local models отсутствуют; actual report предоставлен пользователем. Source review проведена ассистентом, не независимым человеком.

| Нюанс исходного задания | Проверка actual v14 | Результат |
|---|---|---|
| Обязательный ответ |10 positive answered; all requested parts покрыты direct source prose/code/diagram/table |10/10 |
| Sources:source+section/chunk_id | Metadata/bindings/line bounds;46 selected chunks воспроизведены canonical Day21 fixed |10/10 answers |
| Цитаты из найденных chunks | Catalog/chunk/source/claim identity, exact substrings |53/53 quotes |
| Наличие sources в каждом positive answer | Не пустые trusted source records |10/10 |
| Наличие quotes в каждом positive answer | Не пустые quote records |10/10 |
| Совпадение смысла с цитатами | Manual source inspection; each statement == own source quote; нет free synthesis |10/10 |
| Полнота ответа | Явные isolation/load rules, pre/post stages, tool discovery/routing/verification/recurring output |10/10 |
| Если релевантность ниже порога:не знаю+уточнение | negative02 max cosine0.423014 <0.50, no selected hits,0 structured calls | Пройдено |
| Нет фактов при score выше порога | negative01 max cosine0.520236, selector unknown, insufficient_context, clarify,empty evidence | Пройдено |
| Повторная проверка всех нюансов | Этот полный10+2 reviewed; earlier results не складываются | Пройдено |

Измерения:53 selected/public passages,46 selected chunks,898 catalog fragments,260 final proof units,57 raw proof references,25 model calls,prompt tokens881–7252,все done_reason=stop. Model coverage остаётся7/10, три false01/03/05 вручную приняты. Negative judgments не изменялись. Ноль semantic_verifier_pass ожидается для extractive.

## Итог и ограничения

Original report/summary/results/checks сохранены неизменными. В reviewed добавлен manual_summary.assignment_complete=true; исходный summary.assignment_complete=false был pending manual review. Это завершение исходного задания в explicit diagnostic workflow с manual review; strict-model-coverage10/10 не получен. Программный код совпадает с проверенной v14 поставкой; менялись только reports/docs.

В ответах есть лишние source fragments, RU/EN duplicates, большой code и обрывки на chunk boundaries. Основные прямые цитаты достаточны; качество подачи можно улучшать отдельно. Exact extraction не гарантирует source truth/relevance/completeness на любых будущих questions. Каждый новый прогон требует review; текущая отметка не переносится автоматически.
