# v092 / 0.7.22 — Router сохраняет формулировку документационного вопроса

Mac v091:259 tests passed,59 SHA match,admission6passed,CURRENT44/405 verified.
Ollama0.40.3. Positive serialization RU Doc:1known call,1130input/73output,
answered/completed,0technical failures/retries/unknown attempts/embeddings.
Пропуск explicit no-per-agent copies повторился; selected e1/e2 indirectly
support Documentation/Git concurrency, direct task statement находится в e3.
Этот control не является semantic PASS. Raw7reports,review и exact1input
retained в reports/mac-v091; исходные ответы не исправлены.

## Конкретный дефект входа

Fan-out Router делил текст по и/and/also и ?, отбрасывал части с Git intent,
а все оставшиеся объединял через '? '. Поэтому Documentation и Git превращалось
в Documentation? Git. Это воспроизводимый дефект сохранения вопроса, но его
влияние на наблюдавшийся semantic omission ещё не доказано.

v092 сохраняет исходный delimiter между соседними retained Doc parts и исходный
question mark на их границе. Группы, разделённые исключённым Git intent, соединяет
переводом строки, не выдуманным вопросительным знаком. Новые tests проверяют
RU/EN внутренние союзы, несколько Doc questions и Git intent между/перед ними.
Kind/permissions/ambiguous/write denial patterns прежние; source selection остаётся
ограниченным. Это bounded regex router, не общий semantic intent classifier.

Prompt project-answers-v16 и Single snapshot-single-v17 byte-identical v091.
Generation/schema/text/name guards,Baseline,Main assembly,retrieval/options/lease
unchanged. Original22case catalog/rubric и indexed docs byte-identical.
Schema source-prefix-v6, text policy source-prefix-v3. Нет automatic answer/
citation repair, status promotion, model retry/cloud fallback.

## Verification и новый diagnostic

88local tests passed, including3new routing tests;native expected262.
242historical/native inputs max8179/8192 без truncation;17helper checks passed.
Generation0/embedding0 local. 44historical frames schema-valid/43appaccepted/
1mixed-script guardreject — compatibility, не semantic quality PASS.

Новый derived diagnostic_serialized_ru_v092.json получен из неизменного original
known вопроса текущим Router. Документационный вопрос теперь сохраняет
Documentation и Git и конечный ?. Он отличается от rawv091 control; сохранены
оба варианта. Required two documentation points прежние. Git branch task исключён.
Первый native запуск full262 + ONE positive RU Doc call cap1,FTS,zero embeddings.
Это проверка эффекта изменения входа, не hidden replay прежнего freeze.

Remaining:Main RU inputs/ID omissions; Single irrelevant/Git-citation facts;
serialized no-copy omissions/indirect citations;paraphrase FTS5 omission;полная
регрессия finalversion,independent heldout/human review,3paired repeats,E2E/actual
changed-files Chain,controlled native cold/warm/tokens/RAM/swap,research decision.
Этап7 OPEN;8только после completion notice и согласования с Юрием.
