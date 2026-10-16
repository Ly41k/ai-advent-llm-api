# v095 / 0.7.25 — порядок text → evidence_ids

## Реальный результат v094

Mac Python3.13.3:262tests passed,59Python digests совпадают с релизом,
admission6passed, OllamaGET/api/version0.40.3, CURRENT44docs/405chunks прежний.
Один production Documentation EN request завершён:1knowncall,1020input/76output,
0model/metadata retries,0unknownattempts/embeddings/cloudfallback.
7originalJSON SHA проверены, sources digests/spans/lines проверены локально.
Question/evidence/schema/model/options совпадают с EN Multi Doc inputv093;
системная инструкция изменилась. Final freshness/worker cleanup passed.

Ответ c1 с e1/e3 описывает отдельные Documentation/Main tasks, Git/retrieval
concurrency и serializedcalls/onelease. Separate tasks и sharedlease поддержаны
e1/e3; прямое Git/retrieval concurrency положение находится в e2, но e2не указан.
Ошибка source binding повторилась. Alternative severalQwencopies по-прежнему
явно не разобрана. Повторов смысла в этом ответе нет. Сама архитектурная мысль
есть в полученных источниках; проблема в процитированных IDs, а не выдуманном
факте. Технический PASS не означает semantic acceptance. Полную серию v094не
запрашиваем. Исходные7JSON,originalbundle и separate review сохранены в reports/mac-v094.

## Ограниченная следующая гипотеза

v086–v094 задавали evidence_ids перед text. Модель могла выбрать IDs до того,
как сформулирует составное утверждение, и затем включить часть другой цитаты.
Это возможное объяснение, не установленная причина. v095 запрашивает text перед
evidence_ids в claim properties/required и в format hints Documentation/Single.
Теперь подсказка предлагает сформулировать текст до выбора ссылок. JSONSchema
не определяет семантику порядка полей: изменяется схема, подаваемая backend;
фактический эффект на локальную Qwen проверяем отдельным Mac control.

Prompt project-answers-v19; Single snapshot-single-v20;
Doc schema status-claims-text-first-v7. SOURCE_RULES точно v094, EN781/RU1095bytes.
Application принимает те же JSON-объекты независимо от порядка их ключей.
Обязательность обоих полей, text1..600,1..3unique selected IDs, closed objects,
disjoint unknown/answered/partial branches и source-ASCII prefix contract прежние.
Строгие JSON/string границы защищают от quote/escape/control crossing при text-first;
проверки identifier/script/language/status и terminal lease handling не ослаблены.
Нет автоматического исправления текста/IDs, новой фактологии в prompt, retry,
cloudfallback или restart. Runtime функции generation/baseline прежние кроме
format hints. Router/retrieval/corpus/MainID-only/options8192/1024/temp0/seed31
не изменены. Evaluationfixturev094 содержит только точный input для budget/context
regression; ошибочный nativeanswer не становится goldenanswer.

## Проверки

88affectedlocaltests passed, including string-boundary/identifier/schema/unknown
contracts; syntheticmodeltransport.353historical/nativeinputs max8169/8192,
полные question/evidence без truncation.17helperchecks+13scope/schema/bundlechecks
прошли.44nativev093frames иv094frame остаются структурно допустимыми: эти проверки
не выдают sourcebindingsemanticPASS. Fullnative262 и realQwenqualitypending.

Mac helper: новый262preflight, CURRENTverify/admission/GETversion/source59,
freshfreeze, только ОДИН positive serializedEN Documentation call,cap1,
embeddings0. Не запускает Main/Git-generation или следующийpacket. Bundler сохраняет
исходные7JSON+SHA и partialreports при stopped; существующие outputs не перезаписывает.
CURRENT/bge-m3 НЕ rebuild. После разбора решаем, выдержал ли кандидат целевой
контроль. Нельзя автоматически превращать один удачный ответ в acceptance.

Этап7 OPEN: sourcebinding/сравнение/повторы, finalversionknownregression,
independentheldout/humanreview,3pairedrepeats,productionE2E/actualchanged-filesChain,
controllednativecold/warm/tokens/RAM/swap и исследовательское решение ещё нужны.
После закрытия7 явно сообщить Юрию и согласовать время начала8. Не начинать8автоматически.
