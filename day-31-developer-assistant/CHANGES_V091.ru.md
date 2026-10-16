# v091 / 0.7.21 — явные обе стороны X/Y и лимит claims

Mac v090:259 tests passed,59 Python SHA совпали. CURRENT44 docs/405chunks
неизменён.23 native reports retained byte-for-byte в reports/mac-v090;
21 inference inputs context/message/schema/budget SHA реконструированы.
Четыре packets:8/22 known questions,16 observations,20 calls18716input/1608output.
С отдельным production unknown:21calls19698input/1632output. Technical failures,
model/metadata retries, unknown inference, cloud fallback и embedding calls0.
Это один paired repeat; остальные14 questions не run на v090.

Unknown4/4correct. Serialized:shared lease назван в4ответах, no-agent-copies
лишь в1. RU Multi task-concurrency clause supported indirectly; direct e3 не
выбран. EN Single прежние one-model/Git citation gaps не повторяет, но adds extras.
Main:EN Multi complete/supported. RU ID-ordering/full-question omissions persist;
EN Single adds unrelated Day29 scope and binds live branch to docs, although the
separate application Git observation is correct. Paraphrase:4/4 direct clauses
supported; previous extra-cloud citation gap absent. FTS5 absent all;RU Multi
combines two points. Grammar/provenance/runtime PASS не закрывает качество.

## Candidate change

Общие source instructions требуют явно подтвердить/отвергнуть КАЖДУЮ сторону
вопроса X/Y; сохранить из источника весь список inputs/permissions и технологию/
пределы; выбранные IDs доказывают весь text; остановиться после покрытия вопроса.
Cap claims не цель для заполнения; no duplicates/unrelated facts. Убрана строка
1–5 claims из prompt; JSON schema по-прежнему допускает до5. Изменение направлено
на observed omissions/overexpansion; причинность и semantic effect пока не proven.
RU1108bytes/EN798bytes. Prompt project-answers-v16,Single snapshot-single-v17.
Support-first unknown и language/ASCII строки точно прежние. Answered/partial
условие прежнее за исключением удалённой подсказки количества claims.

Schema source-prefix-v6, text policy source-prefix-v3, guards, Baseline Git-ID-only
instruction, Main assembly, retrieval/options/lease и indexed docs unchanged.
Original22case catalog/rubric unchanged. Нет automatic fact/citation repair,
deduplication, добавления FTS5/ответов, status promotion или model replay.

## Offline and first native control

82local tests passed;241 historical/native inputs max8179/8192 без обрезки.
17helper checks passed;44 historical frames schema-valid,43app accepted,1old
mixed-script name rejected. Эти проверки синтетические/структурные, не quality PASS.
Native full259 и реальные ответы v091 pending. CURRENT не rebuild.

Первый запуск: [Mac procedure](RESEARCH_MAC_V091.ru.md),1 positive RU Documentation
control serialized-doc-ru,cap1. Новый derived diagnostic сохраняет точный scoped
Documentation input прежнего known serialized-model-branch-ru; live branch
исключён. Original catalog/rubric не переписан; только отдельный derived Doc case.
Required points сохраняют одну Qwen/no copies и serial calls/shared lease with
Git/retrieval concurrency; это known diagnostic, не heldout/full pair.

Действующий Router в fan-out разделяет союзы и соединяет оставшиеся Doc fragments
через question mark. Поэтому точный scoped input содержит Documentation? Git.
Derived control повторно маршрутизируется идентично (checked). Это известное
ограничение сохранения формулировки, которое нужно отдельно исследовать;
текущий control сравнивает прежний exact role input, не исправляет вопрос скрыто.

Этап7 OPEN: complete final-version known regression, independent heldout/human
review,3repeats,E2E/actual changed-files Chain,controlled native cold/warm/tokens/
RAM/swap и research decision. Этап8 после уведомления о закрытии7 и соглашения
с Юрием о времени начала.
