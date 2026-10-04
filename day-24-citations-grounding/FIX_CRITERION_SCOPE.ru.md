> Историческое описание v13. Current v14: strict сохранён; separate diagnostic policy — START_HERE.ru.md и FIX_DIAGNOSTIC_POLICY.ru.md. Actual v13:8/10 +2/2, не завершено.

# v13: границы критериев полноты

Полный v12 дал8/10 подтверждённых ответов,41 точную цитату и2/2 правильных negatives. Источники всех кандидатов и255 final proof units сверены с corpus;99 raw proof ID references соответствуют v12 resolver. Отказы01/09 не считаются выполненными.

## Что меняется

- Обычный вопрос how/как получает один mechanism criterion, который требует concrete rules/steps для ВСЕХ частей исходного вопроса. Дублирующая общая question gate удалена. В v12 на01 mechanism=true, question=false без конкретной missing part: это два конкурирующих judgments одной обязанности. Для what/where/names/counts общая question gate сохраняется.
- Verification questions сохраняют question/action/observation. Question проверяет полную связь ответа с исходным вопросом. Action проверяет конкретные действия проверки. Observation проверяет ожидаемый output/state/flag; route/commands/full answer проверяются другими gates. Topic остаётся в question_context.
- Prompt формируется по criterion до данных. Проверка получает only its task; нет списка смешанных заданий для всех критериев. В v12 observation09 ошибочно требует routing после фильтрации action units, хотя verified=true доступен в независимом source unit.
- Proof ID enum, runtime ownership, command/action exclusion, threshold, exact source identity, unknown и bounded retries сохраняются. False нового прогона не превращается в true. Original v12 report сохранён неизменённым.

## Проверки и пределы

109 tests Дня24 (103 предыдущих+6 scoping tests) и34 регрессии. Новые tests проверяют all-parts obligation, отдельный observation/action prompt, what/count/verify gates, отказ при negative mechanism, contract replay saved01 и authored outcome на actual09 source. Replay/author fixtures не являются новым live v13 inference; нельзя объявлять10/10 по этим tests. Coverage model может ошибаться и после уточнения prompt.

Осталась ручная проверка полного evaluate_v13.json на MacM1/32GB с bge-m3/qwen2.5:14b. Возможные лишние passages/duplicates/cut boundaries ещё не устранены этим исправлением. Сначала all10+2, затем source/relevance/completeness review. Новый индекс/модели не требуются.
