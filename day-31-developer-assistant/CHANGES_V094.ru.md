# v094 / 0.7.24 — поддержка всех частей claim выбранными IDs

## Подтверждённые результаты v093

Mac Python3.13.3:262 tests passed,59 Python digests совпали. Один paired repeat
для22 известных RU/EN вопросов дал44 ответа и54 known generation calls;
50134 input /3781 output tokens,0 technical failures/retries/unknown attempts/
embeddings. Отдельный production RU untracked Doc control:1call,1055/70tokens.
Итого55calls,51189/3851tokens. CURRENT44docs/405chunks прежний.
Это known regression, не held-out, реальный E2E или resource acceptance.

39 из40 содержательных ответов имеют поддержку всех опубликованных частей
выбранными цитатами; ещё4unknown controls корректно воздерживаются с claims=[].
Это не оценка общей полноты и не39/40quality acceptance.
В serialized-model-branch-en/Multi/c1 утверждение о Git/retrieval concurrency
поддерживает e2, но опубликованы только e1/e3. Сам факт есть в выбранном корпусе;
ошибка именно в привязке части текста к процитированным IDs. Main сохранил IDs.
Повтор смысла остался в uncertain-branch-ru/Multi и появился в dense-private-branch-en/Multi.
Прежние ошибки untracked/Day18 и paraphrase/cloud не повторились в одном наблюдении.
RU assistant/language теперь без повторов, но это ещё не доказанная стабильность.

Отдельно остаются пропуски: serialized трижды не раскрывает альтернативу отдельных
копий Qwen; Main пропускает полный вопрос/порядок IDs; paraphrase не называет FTS5;
paths не называет exact relative path/not basename; uncertain EN Single не называет
recovery. Dense новые-layer формулировки пересекаются по смыслу с прямым ответом,
поэтому literal omissions нельзя объявлять четырьмя фактическими ошибками.
EN language keep original text семантически покрывает отсутствие замены переводом.
Рубрики и native ответы не переписаны ради PASS.

reports/mac-v093 сохраняет51 исходный JSON byte-for-byte,12 исходных bundles,
12reviews и полную сводку; evaluation/prompt_input_regression_v093.json содержит55
точных inputs для context/budget regression, не золотые ответы или held-out.

## Ограниченное изменение

Общие SOURCE_RULES теперь явно требуют: весь claim следует из выбранных IDs;
часть другой цитаты требует её ID, иначе её следует убрать. Один факт — один раз
во всём ответе, включая повтор внутри одного text. Перефразирование или другая
цитата не превращают тот же факт в новый. Сохраняются все части/альтернативы,
релевантные входы/права, технология, пределы и область.
Prompt project-answers-v18, Single snapshot-single-v19. EN781bytes/RU1095bytes,
оба короче v093. Первые support/language строки и последнее status правило прежние.
Это инструкция модели, не semantic entailment verifier и не доказанное исправление.
Нет topic/case-specific expected facts/IDs/paths в production prompts. Нет app
answer repair, автоматического добавления IDs, status promotion или retry.
Schema source-prefix-v6, identifier/text guards, options8192/1024/temp0/seed31,
Router, corpus/retrieval, Main ID-only, budget/lease и transport прежние.

## Проверка кандидата

88 affected tests passed на local Python3.12, model transport synthetic.
352 historical/native inputs max8169/8192, полные questions/evidence сохранены.
17helper checks и11scope/bundle checks прошли без model operations. Все44native
v093 frames schema/application valid, включая известную ошибку привязки — guards
не являются semantic verifier. RuntimeAST generation/baseline отличается только
prompt/version assignments. Native262test preflight и real Qwen quality на Mac
ещё pending. Helpers создают
один bundle как при успехе, так и при частичном сбое; исходные JSON не заменяются.
One positive EN Documentation control повторяет scoped serialized-model вопрос
из v093. Cap1, fresh freeze, no Git/Main generation. Это известный control,
не held-out, paired repeat или независимая оценка. Он проверяет source binding,
обе альтернативы и отсутствие повторов на реальной Qwen. Автоматически следующий
packet не запускается. CURRENT и bge-m3 не пересобирать.

После review control: unknown guard и targeted serialized/uncertain/dense pairs,
затем итоговая known regression выбранной версии. Не запускать всё сразу.
Остаток этапа7: устойчивое качество, независимые held-out/human checks,3paired
repeats, productionE2E/actual changed-filesChain, native controlledcold/warm,
tokens/RAM/swap, исследовательское решение. Этап7 OPEN. После закрытия уведомить
Юрия и согласовать начало8; этап8 автоматически не начинать.
