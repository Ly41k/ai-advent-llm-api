# v085 / 0.7.15: проверка поддержки перед раскрытием вопроса

В native v084 unknown-пакет остановился на первом RU Multi. Ollama завершила
один HTTP chat: 999 input / 88 output tokens. App отклонил ответ с
`unsupported_identifier`; claims/citations не опубликованы. Остальные три
наблюдения не запущены. Это не unknown inference: worker reaped, FINAL_VERIFY
passed, условия после запроса совпали. Завершённый reply закрывает lease до
проверки содержимого; этот отказ сам по себе не требует restart/recovery.
Raw rejected text не сохранён, поэтому точный идентификатор и формулировка
неизвестны. Повтор имени из вопроса в описании отсутствия — возможное объяснение,
а не установленная причина. Неизменённые JSON и отдельный разбор — reports/mac-v084.

Shared Documentation/benchmark Single instructions теперь сначала требуют
проверить поддержку, затем при отсутствии возвращать unknown и пустой claims.
Общие сведения не доказывают названную сущность/параметры. Неподтверждённые имена
не повторяются даже в отказе; описание отсутствия сведений не становится claim.
Далее идут язык, цитаты, сравнения, запреты, входы/действия компонента и полнота.
Правила общие: без fixture IDs, golden paths или ответов на известные вопросы.
Prompt `project-answers-v10`, Single `snapshot-single-v11`.

`unsupported_identifier` остаётся включённым. Server DOC schema v5, bounded text,
identifier spelling guard, production Main ID-only contract, Single combined
context, retrieval, model/options, leases и budgets прежние. Нет автоповтора,
текстового ремонта, принудительного unknown по case ID или semantic PASS.
Это prompt experiment; реальное исправление качества пока не подтверждено.

Изменены 3 production Python и 4 test Python. В существующем negative regression
расширена синтетическая проверка: RU/EN × Documentation/Single completed refusal
отклоняется, ровно один call, lease закрыт, без retry и текста в diagnostics;
корректный empty unknown допускается. Native count остаётся 256, Python files 59.

Локально: 41 affected + 7 boundary/language tests прошли. Первый запуск имел два
import errors из-за отсутствия jsonschema на sys.path; исходный report сохранён,
те же sources перепроверены с уже установленным изолированным jsonschema4.25.1.
94 исходных контекста помещаются без изменения evidence: max8153/8192.
44 старых decoded frames проходят независимый JSON Schema; старый Мain frame
по-прежнему отклонён guard. Это не semantic acceptance этих ответов.
17 helper/plan checks прошли, model/embedding calls 0; shell transport fixtures
явно синтетические. Native v085 256 tests и реальный Qwen ещё pending.

## Что осталось до закрытия этапа 7

1. Проверить unknown v085 на Mac, затем полный RU/EN Single/Multi known regression
   на закреплённой итоговой версии. Сейчас serialized v084 RU Multi не раскрывает
   serial lease и не цитирует e2 для no-copy; EN Single привязывает текущую ветку
   к архитектурным цитатам, хотя отдельный Git факт верен. Эти проблемы не закрыты.
   В полном v083 также остались детали fixed rubric Main/FTS5 и uncertain coverage.
2. Независимые новые/held-out вопросы и human review. Известные кейсы и Codex
   разбор не подменяют независимую приёмку.
3. Три парных repeats с фиксированными conditions/order; current end-to-end
   проверка отдельно от paired snapshot smoke.
4. Контролируемые native cold/warm, tokens, RAM/swap и исследовательский вывод
   Single/Multi без вывода о скорости из неконтролируемых smoke timings.

Этап 7 открыт. После его завершения сообщить Юрию и согласовать, когда начинать
этап 8. Этап 8 автоматически не запускать.
