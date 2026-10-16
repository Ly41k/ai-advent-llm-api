# v086 / 0.7.16 — точные ASCII-имена в начале русского claim

## Native v085: итог, который не является PASS

Все 11 пакетов были начаты. Десять завершились; main остановился на RU Multi.
20 вопросов имеют полные пары / 40 завершённых ответов. Ещё один ответ
Documentation отклонён, RU Single и оба EN пакета main не получены.
49 известных Qwen calls, 46023 input / 3598 output tokens; 1 technical failure,
unknown inference / retries / embeddings — 0. Отдельный production unknown RU:
1 call, 985 input / 24 output, корректный unknown. Его не считаем paired repeat.
Native preflight v085: 256 tests / 59 SHA passed, index 44/405 verified.
49 inference inputs/context/message/schema/budgets реконструированы и совпали с SHA.
Исходные JSON без изменений и отдельные reviews: reports/mac-v085.

Открытые результаты:
- main RU Documentation: identifier_script_mismatch. HTTP chat completed,
  1186 input / 124 output, raw rejected text не сохранён. Точное имя неизвестно;
  нельзя утверждать, что это обязательно Main. Main assembly не запускался.
  Worker reaped, FINAL_VERIFY passed, Git main проверен отдельно. Это известный
  завершённый вызов, не uncertain inference; сам отказ не требует restart.
- serialized EN Multi: no-copy clause использует e1/e3 вместо прямого e2.
- paraphrase EN Multi: незапрошенная фраза no cloud LLM берётся из e2, а cites e1.
  Все четыре отвечают на прямые вопросы, но не называют FTS5 из broader rubric.
  expected_source_present=false у EN — hint другого namespace; Day30 README
  подтверждает прямые ответы, это не выдуманные источники.
- paths EN Multi: source «документ может описывать часть» усилен до категоричной
  связи с частью функциональности. Основные пункты верны, добавка не установлена.
- uncertain RU Single: не отвергнут явно automatic replay. RU Multi повторяет
  cloud fallback prohibition в двух claims. Оба EN отвечают полностью.
- assistant EN Single: поддержанный, но незапрошенный SQLite/history тезис.
- Несколько RU answers соединяют два пункта вопроса в одном claim.

## Что изменено

v085 RU pattern требовал первой русской буквы. Это может создавать конфликт
с точным ASCII-именем в начале предложения; это гипотеза о стимуле формата,
не реконструкция отсутствующего raw ответа. v086 позволяет exact source ASCII
prefix перед русской прозой. Например, source Main допускает Main получает...
без необходимости изменять M или вставлять дополнительный русский заголовок.

Префиксы берутся только из переданных evidence quotes: первые 32 уникальных
ASCII-слова с заглавной первой буквой, длиной 2–32 символа. Question, rubric и
case IDs их не задают. Это ограниченный механизм написания, не классификатор
technical entities. Если слово не вошло в bounded список, можно начать с русского
слова и сохранить supported ASCII-имя дальше. Список не меняет источники/поиск.
После ASCII-prefix требуется один пробел и русская буква. EN pattern прежний.

Каждая regex alternative сама ограничивает ВЕСЬ claim 600 символами, включая
prefix. ASCII quote/backslash и line/control chars запрещены как раньше.
Никаких lookaround в dispatch pattern или зависимости от server maxLength.
Одинаковый pattern проверяется server schema и application start guard.
Pure English в RU, произвольный prefix из вопроса и подменённые буквы отклоняются.
`cited-ascii-name-script-v1` и unsupported_identifier сохранены; text не исправляется,
автоматических повторов/добавления citations/deduplication нет.

DOC schema: status-claims-source-prefix-v6.
Text policy: json-safe-source-prefix-v3.
Shared prompt: project-answers-v11; benchmark Single: snapshot-single-v12.
Main по-прежнему получает только full question, checked claims и application Git
facts, без source excerpts, и выбирает существующие IDs; нового текста не создаёт.

Общие инструкции требуют факты только из ВЫБРАННЫХ цитат, не соседних excerpts;
один пункт вопроса на claim, без повторов/лишних фактов; сохранение «может»,
отрицаний и границ; явное отклонение неверной альтернативы; нужные входы/действия/
запреты компонента и технологию/пределы механизма. Нет fixture facts/paths/answers.
Это candidate correction: новая семантика ещё не принята. Ни JSON Schema, ни
spelling guard не доказывают entailment или полную поддержку каждой фразы.
Исходный catalog v077 и required_points не менялись; no automatic semantic PASS.

## Проверки и ограничения

82 affected local tests passed; транспорт модели/lease responses синтетические.
Новые тесты проверяют exact prefix в обоих clients, regex length600/601 независимо
от maxLength, источник prefixes/лимит32, JSON fences и отсутствие обхода app guard.
143 input contexts (40 historical +54 v083 +49 v085) помещаются без изменения
evidence: max8140/8192. 44 старых decoded frames schema-valid; app по-прежнему
отклоняет один старый Мain frame. Это не semantic PASS остальных 43.
17 shell-flow/source-guard/real zero-model CLI-plan checks passed с fake transport.
259 full native tests ожидаются на Mac; Python files остаются 59.
Inspection сохранённого pinned converter source показывает поддержку literal
alternatives, non-capturing groups и finite quantifiers. Сам native converter и
Qwen с новой schema здесь не запускались: это проверит один Mac control.

Corpus, bge-m3 index 44/405, retrieval, model/options и lease policy прежние.
Новый budget fixture — только regression входов, включая rejected Main input;
не golden answers, не held-out и не production model instruction.

## До закрытия этапа 7

1. Проверить новый формат на real Mac и устранить оставшиеся semantic/citation/
   coverage замечания; выполнить полную регрессию на итоговой закреплённой версии.
2. Независимые новые/held-out вопросы и human review.
3. Три paired repeats и current-version end-to-end отдельно от snapshot smoke.
4. Контролируемые native cold/warm/tokens/RAM/swap и исследовательский вывод.

Этап 7 OPEN. После его завершения уведомить Юрия и согласовать, когда начинать 8.
Этап 8 автоматически не запускать.
