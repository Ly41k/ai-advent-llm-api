> Исторический разбор. Для текущей v14 следуйте START_HERE.ru.md и FIX_DIAGNOSTIC_POLICY.ru.md.

> Историческое описание v11. Текущая версия — v13; см. START_HERE.ru.md и FIX_CRITERION_SCOPE.ru.md. Полный v11 проверен:3/10 +2/2; не используйте его как итоговую версию.

# v11: один coverage criterion — один verdict

Реальный v10: automatic/manual4/5. Все24 опубликованных цитаты дословны; source bindings проверены. №09 имеет полный source answer, но coverage дважды вернул question, а action/observation ссылаются на одну comparison sentence. №10 содержит нужные source passages, но его model proof ошибочно считает journalctl-command результатом, поскольку она внутри action excerpt.

1. Каждый criterion проверяется отдельным model call с schema reason/answer_excerpt/covered. Модель не задаёт ID и не возвращает массив. ID привязывает приложение; затем валидирует общий состав/complete verdict. Это устраняет application-причину duplicate/missing IDs, не исправляет semantic false автоматически.
2. Для strict режима action и observation не могут совпадать или содержаться друг в друге после whitespace normalization. Поэтому кусок command block больше не принимается как отдельный result. Negatives не превращаются в positives; старый negative-excerpt format repair сохраняется и оставляет false.
3. Python passages оформляются code fences; source text/claim/quote/строки не меняются. Selector просится выбирать минимальный достаточный набор вместо постоянных6/duplicates/example clutter; качество такого выбора нужно оценить live, это не гарантируется prompt.

93 теста Дня24+34 regression=127PASS.6 новых тестов: настоящий duplicate-batch v10№09 нельзя использовать в single-verdict schema; настоящий selected context09 публикуется только с авторскими корректными отдельными criterion verdicts; model ID injection запрещено; настоящий nested command-proof10 блокируется; fresh retry требует отдельный результат; code presentation сохраняет exact identity. Авторские passage choices/verdicts — fixtures, не успех Qwen.

Scripted strict10+2 проходят. Default proof_kind=verbatim_source_identity, semantic_verifier counters0 честно сохраняются. Corpus/index/retrieval/порог/model names остаются прежними, только Д24 меняется. За попытку теперь1selector+1–3coverage calls; до2attempts. Никаких готовых ответов, question IDs или gold sources в production.

Применить по START_HERE.ru.md и перейти к полному10+2. Новый v11 ещё не измерен на пользовательском Ollama; не объединять прошлые4 успеха с другим прогоном в искусственный10/10. Требуется проверить все10 новых ответов и оба negative controls.
