# v096 / 0.7.26 — отвечать на вопрос, не только повторять условие

## Проверенная v095

Mac Python3.13.3:262tests/59SHA совпали с выпуском. CURRENT44docs/405chunks
и corpusrevision прежние. One EN production Doc control:1call1020/61tokens,
поддержанный прямой выбор serializedcalls/onelease; broader rubric не полна.
Unknown RU/EN Single/Multi:4/4 корректные abstentions с claims/citations=[],
4calls3570/100tokens, без technicalfailures или inventedparameters.

Serialized RU/EN paired:4observations,6calls5029/304tokens,0technicalfailures,
model/metadataretries,unknownattempts,embeddings/cloudfallback. Все опубликованные
части поддержаны выбранными цитатами, все4ветки main повторно наблюдались черезGit.
Но RU Multi ответил только «Documentation и Git могут выполняться параллельно;
Verification проверяет их результаты». Это правильные исходные факты, которые
не отвечают на центральное «несколько копий или последовательные вызовы».
RU Single иобаEN ответа выбирают serialcalls/sharedlease. Прямой выбор считается
семантически корректным без дублирующего буквального «не несколько копий»;
более широкие пункты immutable rubric всё равно явно не раскрыты. Fullrubric0/4.
EN Multi reproduces positiveDoccontrol на том же входе; RUregression показывает,
почему одного ENcontrol недостаточно. Main сохранил claim и Gitfact; пропуск
возник в Documentation, не в ID-only сборке. Повторов и source-binding gaps
в этой короткой серии не обнаружено. Fullv095regression не запрашиваем.

Итогоv095:10pairedcalls+1control=11calls,9619input/465outputtokens,
4/22knownquestions с одним pairedrepeat. Не heldout/E2E/resources acceptance.
reports/mac-v095 сохраняет15originalJSON,3originalbundles и3separate reviews.
Evaluationinputfixturev095:11 exactnativecontexts для budget/context regression,
не золотые ответы. Неуспешный по полноте RUanswer не переписан в PASS.

## Ограниченное изменение

Shared SOURCE_RULES теперь ставят прямой вывод перед повторением premise/условия
вопроса и требуют разрешать все части и альтернативы. Поддержка выбраннымиIDs,
релевантные входы/права/технология/пределы/область и отсутствие повторов сохраняются.
Первые support/language строки и последняя status строка точны какv095. EN779bytes,
RU1090bytes, короче v095. Нет Qwen/lease/serialized-case facts, fixture IDs,
expectedanswerphrases или sourcepaths в productionrules. Одинаковые правила
используют Single/Multi. Это общая модельная инструкция, не deterministic verifier
и не доказанное исправление. Дополнительных modelcalls в pipeline нет.

Prompt project-answers-v20; Single snapshot-single-v21. Schema text-first-v7,
closedobjects/requiredfields/text1..600/IDs1..3unique/sourceprefix/JSONboundaries/
identifierguards/statusbranches прежние. Нет automaticanswerrepair/citationappend/
statuspromotion/retry/cloud/restart. Generation/baseline runtimeAST меняется
только в rules/versionassignments. Router/retrieval/corpus/MainID-only/budget/
lease/modeloptions прежние. Один modeloperation черезsharedlease.

## Верификация и Maccontrol

88affectedlocaltests passed, transportsynthetic.364historical/nativeinputs,
max8164/8192, без сокращения question/evidence.17helperchecks+13schema/scope/bundle
checks passed; priornativeframes остаются schema-valid, что не доказывает качество.
Nativev096262 и actualQwen effect pending.

Helper выполняет новый262nativepreflight, CURRENTverify/admission6/GETversion,
source59/catalog/diagnosticplanguard,freshfreeze, только ОДИН positive RU Doc
call,cap1. Question совпадает с scoped RU Multiv095; actualevidence проверяем по
новому report, не обещаем одинаковый snapshot заранее. Embeddings0;нет Main/Git
generation или auto-nextpacket. Один bundle включает7originalreports+SHA;
при stopped сохраняются доступные reports,missingfiles иненулевойexitcode.
CURRENT/bge-m3 НЕ rebuild. Сначала review RUcontrol; потом отдельные targetedpairs.

Этап7 OPEN: прямое качество/grounding/полнота/повторы, finalversionknownregression,
independentheldout/humanreview,3pairedrepeats,productionE2E/actualchanged-filesChain,
controllednativecold/warm/tokens/RAM/swap и researchdecision ещё нужны.
Когда этап7 закрыт — явно сообщить Юрию и согласовать время начала8. Не начинать8автоматически.
