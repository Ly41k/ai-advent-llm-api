# v090 / 0.7.20 — полные предложения источников и отдельные пункты

## Проверенный Mac v089

Python3.13.3: 259 tests, 59 Python SHA совпали. CURRENT остаётся 44 docs / 405
chunks, index 27519cd6caa346ac87a18639932506b5. Ollama 0.40.3. Шесть targeted
packets: 12 из 22 known questions, 24 observations, один paired repeat.
32 known generations, 29061 input / 2530 output tokens. Вместе с отдельным
production Main Documentation RU control: 33 calls, 30271 / 2665 tokens.
Ошибки транспорта, retries, unknown inference, cloud fallback и embeddings: 0.
Все 33 native inference context/message/schema/budget SHA реконструированы.
31 исходный native JSON сохранён byte-for-byte; семь reviews, сводка и fixture
отдельно в reports/mac-v089. Повторные вложения с (1) не являются новыми trials.

Unknown: 4/4 correct. Main: все четыре answered, но RU Multi не называет ID
ordering; RU Single также не называет полный вопрос; EN Single дублирует claim.
Serialized: только RU Single complete/supported. RU Multi пропускает serial
calls/lease; EN Multi пропускает no-per-agent-copies. EN Single c3 указывает
architecture e1 вместо прямого support e2; c5 связывает live branch с docs e1,
хотя отдельный app Git fact корректен. Есть повтор и лишние поддержанные факты.
Paths: 4/4 content/citations correct; прежнее категоричное уточнение EN Multi
не повторилось. RU Multi объединяет два вопроса в один claim.
Paraphrase: direct questions correct 4/4, но FTS5 отсутствует во всех ответах;
EN Multi добавляет no-cloud без прямого e2 support, RU Multi объединяет пункты.
Uncertain: 4/4 policy/citations correct, включая no automatic replay в RU Single.
Оба Multi повторяют запрет cloud fallback. Это normal Q&A, не реальная потеря
HTTP-ответа/recovery drill. Semantic acceptance остаётся not_evaluated.

## Изменение v090

Support-first/unknown и язык/ASCII spelling строки сохранены точно из v089,
как и последняя answered/partial строка. Переписаны средние общие instructions:
отдельный claim на пункт, обе стороны X/Y, отсутствие повторов; выбрать IDs
полного предложения источника с нужным фактом, переводить/сокращать с сохранением
условий, не дополнять; полный набор входов/прав компонента, технология/пределы
механизма; каждая часть text должна быть доказана выбранными IDs. RU1092 bytes,
EN843 bytes. Prompt project-answers-v15, Single snapshot-single-v16.
В benchmark-only Single дополнительно явно запрещён текст Git facts внутри
claims: Git передаётся только через git_fact_ids и отображается приложением.

Это общий prompt, без case labels, expected facts, golden IDs или путей.
Изменение является кандидатом исправления, не доказанным semantic PASS.
Нет автоматической правки claims/цитат, deduplication, дописывания FTS5/IDs,
partial→answered, retry или cloud fallback. Native выводы никогда не чинятся.
Schema source-prefix-v6, text policy source-prefix-v3, identifier guards,
Main ID-only assembler, retrieval/options/budget/lease и indexed docs unchanged.
Original known catalog/rubric неизменны. Полная документация/вопрос сохраняются.

## Offline

82 affected tests passed, synthetic transport; 220 исторических/native inputs,
max8163/8192 без truncation. Новый fixture содержит 33 точных входа v089, без
answer targets; это known input regression, не heldout. 17 helper checks passed.
44 старых frames independently JSON Schema-valid; app accepts43 и отвергает
исторический mixed-script Main. Это compatibility, не semantic PASS43.
Два промежуточных локальных отчёта retained: первый обнаружил budget overflow
и missing local jsonschema path; второй — overflow нового v089 input. Инструкции
сокращены, dependency path исправлен в проверяющем окружении; исходные отчёты
не переписаны. Dependencies приложения прежние. Full native v090259 pending.

## Следующий запуск

[Mac procedure](RESEARCH_MAC_V090.ru.md): full native suite, index/admission,
source guard и один RU unknown Documentation control, cap1. Затем по review
paired unknown cap4 и serialized cap6/Main cap6. Никаких automatic loops/replays.
Existing CURRENT не rebuild; preflight строит отдельный temporary FTS smoke.

Этап7 OPEN: final-version complete known regression, independent heldout/human
review, 3 paired repeats, E2E/actual changed-files Chain, controlled native
cold/warm/tokens/RAM/swap и research decision. Этап8 только после уведомления
о закрытии7 и согласования с Юрием, когда его начинать.
