# v097 / 0.7.27 — сохранять отрицания и область условий

## Что показала v096 на Mac

Native preflight: 262 теста, 59 Python SHA совпали с выпуском. CURRENT прежний:
44 документа / 405 чанков. Unknown RU/EN Single/Multi: 4/4 корректных отказа без
придуманных параметров. Serialized: 4/4 ответа дают прямой выбор последовательных
модельных вызовов через общую lease, опубликованные части поддержаны цитатами.
Пропуск центрального вывода в RU Multi v095 в этом запуске отсутствует.
Более широкие пункты rubric про отдельные копии и Git/retrieval явно не раскрыты;
прямой ответ и полная immutable rubric оцениваются отдельно.

Uncertain: 4 ответа, 6 вызовов, 5103 input / 423 output tokens; технических ошибок,
retry, unknown attempts, embedding calls и cloud fallback нет. Источники, схемы,
контексты, snapshot, Main IDs и Git branch прошли техническую проверку. Но:

- RU Multi повторяет запрет cloud fallback во втором claim.
- EN Multi пишет, что automatic replay, cloud fallback и model restart
  «are not automatic and require a verified recovery». Эта конструкция связывает
  условие recovery со всем перечнем запретов. Источники разделяют запрет
  автоматических действий и требование проверяемого recovery. Ответ двусмыслен:
  он не говорит явно, что cloud разрешён после recovery, но и не сохраняет
  однозначно исходную политику. Релевантные IDs сами по себе этого не исправляют.
- EN Single прямо сохраняет uncertain state и запрещает automatic cloud fallback,
  но более широкие пункты replay/restart/recovery явно не раскрывает.

Реальное прерывание HTTP/recovery этим snapshot smoke не тестировалось.
Полную v096 regression не продолжаем. Всего: 6/22 известных вопросов,
12 paired observations / 16 paired calls; с отдельным RU control — 17 calls,
14839 input / 938 output tokens. Это не held-out, E2E или semantic acceptance.
В reports/mac-v096 сохранены 19 исходных JSON, 4 исходных bundle и 4 отдельных
review. Evaluation fixture v096 содержит 17 точных native inputs, не эталонные
ответы; спорные ответы сохранены без переписывания в PASS.

## Ограниченное изменение v097

Общие SOURCE_RULES требуют прямого ответа на все части и сохранения субъектов,
отрицаний и условий; запрет нельзя превращать в условное разрешение. Повтор
одного смысла запрещён также внутри одного text. Каждая часть должна следовать
своим выбранным IDs. Первые строки поддержки/языка и последняя строка status
сохранены точно. EN rules: 789 bytes (+10), RU: 1095 bytes (+5).
Это уточнение модельной инструкции, не проверка смыслового следования кодом.
Ранее перечисленные общие измерения входов/прав/технологии заменены фокусом на
субъектах/отрицаниях/условиях; полного сохранения всех прежних формулировок нет.
Нет имен кейсов, путей источников или готовых фактов uncertain в production rules.

Prompt project-answers-v21, Single snapshot-single-v22. Schema text-first-v7
прежняя, включая closed objects, required fields, text 1..600, IDs 1..3 unique,
языковые/identifier guards и ветви status. Runtime AST generation/baseline
изменён только в rules/version assignments. Router, retrieval, corpus, Main
ID-only, budget, lease и model options прежние. Дополнительных модельных вызовов,
answer repair, citation append, status promotion, retry/cloud/restart нет.

## Проверки и следующий запуск

88 локальных тестов прошли с синтетическим transport. Для 381 сохранённого
контекста budget estimate <=8192, максимум 8169, без сокращения evidence.
Это консервативная оценка UTF-8 плюс allowance/reserves, не измерение tokenizer.
17 helper и 13 invariant/schema/bundle checks прошли. Сохранённые native frames
остаются schema-valid, включая смысловые ошибки: schema PASS не доказывает качество.
Native v097 262 и эффект реального Qwen пока не проверены.

Первый Mac helper: новый 262-test preflight, CURRENT verify, admission, GET version,
59-source/catalog/diagnostic-plan guards, fresh freeze и ОДИН EN Documentation
control (generation cap1, embeddings0). Вопрос совпадает со scoped Documentation
входом EN Multi v096; выбранные evidence сверяем по новому report. Это известный
контроль, не независимый held-out. Нет Main/Git generation или автоматического
следующего пакета. Bundle сохраняет 7 original reports с SHA; при ошибке —
доступные reports, missing_files и исходный ненулевой exit code.
CURRENT/bge-m3 не пересобирать. Инструкция: [RESEARCH_MAC_V097.ru.md](RESEARCH_MAC_V097.ru.md).

## До закрытия этапа 7

- Качество, grounding, полнота и отсутствие повторов на итоговой версии;
  полная известная regression после контрольных вопросов.
- Независимые held-out вопросы и human review; Codex review их не заменяет.
- Три paired repeats на зафиксированной итоговой версии.
- Production E2E, включая actual changed-files Chain.
- Контролируемые native cold/warm замеры, tokens, RAM/swap и research decision.

Этап 7 OPEN. После закрытия явно сообщить Юрию и согласовать время начала этапа 8.
Этап 8 автоматически не начинать.
