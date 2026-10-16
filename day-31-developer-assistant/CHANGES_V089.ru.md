# v089 / 0.7.19 — явный статус answered / partial

## Native v088

Mac Python3.13.3:259 tests passed;59 Python SHA совпали. Existing CURRENT
44 docs/405 chunks verified, index 27519cd6caa346ac87a18639932506b5 неизменён.
Ollama GET /api/version 0.40.3. Production RU unknown: 1 call,999 input/24 output.
Paired unknown:4/4 correct empty unknown,4calls3586input/101output.

Main:4 опубликованных partial ответа,6 known calls5365input/520output.
Транспорт, schema, validators, source freshness и reobserved Git main прошли.
Все task outputs completed/validation passed. Main assembly содержит отдельный
контекст без source quotes и сохраняет переданные IDs. Фактические claims
поддержаны выбранными цитатами, ASCII Main сохраняется. Все четыре имеют
diagnostics=[documentation_partial]; expected answer_status check=false.
Парное исследование completed/technical failures0 не означает semantic PASS.

EN Multi стал полнее: полный вопрос, checked claims, application-produced
Git facts и ID ordering присутствуют. Его fixed rubric coverage complete,
но explicit rejection original excerpts в X/Y не названо. В RU обоих и EN
Single полный вопрос не назван; в RU также нет ID ordering. Все четыре
необоснованно называют ответ partial, хотя источники поддерживают прямые
вопросы. Программа корректно сохраняет модельный partial, не повышает его.

Всего paired v088:4/22 known questions,8observations,10calls8951input/621output.
С production control:11calls9950input/645output. Technical failures/retries/
unknown inference/cloud fallback/embeddings0. Остальные18 known questions не
run на v088. 11 exact native inference context/message/schema/budget SHA
независимо реконструированы. Все15 native JSON сохранены byte-for-byte в
reports/mac-v088, reviews/summary отдельно. Human/held-out acceptance pending.

## Ограниченное изменение

В v088 при сокращении shared instructions исчезло явное условие answered
для поддержанных вопросов и уточнение, что Git/язык/отрицание не являются
пробелом поддержки. Это кандидат причины общего partial, не изолированное
экспериментальное доказательство причинности.

v089 меняет только последнюю строку общих RU/EN rules:

```text
Поддержка всех частей: answered; пробел: partial. Git/язык/отрицание не пробел. 1–5 claims.
All parts supported: answered; partial only for a support gap, not Git/language/negation. 1–5 claims.
```

Support-first unknown, точные ASCII names, отдельные пункты, выбор supporting
IDs для каждого claim, отсутствие дублей и сохранение qualifiers из v088
остаются точно прежними. RU1175bytes/EN823bytes. Prompt project-answers-v14;
Single snapshot-single-v15. Общие правила совпадают между обоими modes.

Нет автоматического partial→answered, semantic status forcing, text rewrite,
append citation IDs или retries. Valid partial остаётся valid partial;
существующий соответствующий transport test прошёл. DOC schema source-prefix-v6,
text policy source-prefix-v3, identifier/script guards, Main ID-only code,
retrieval/options/budget/lease и indexed docs unchanged. Original known catalog
SHA/rubric неизменны. Новый номер prompt не закрывает замечания к качеству.

## Offline verification

82 affected tests passed, synthetic model transport.187 exact historical
input budgets, max8181/8192, без truncation. Новый fixture11 native v088
inputs не содержит answer targets и не является held-out. Case labels не
передаются в model instructions.44 historical frames validate independently
against JSON Schema; app accepts43 и отвергает старый mixed-script Main.
Это format compatibility, не semantic PASS43.17 helper/source-guard/real
zero-model CLI-plan checks passed с явно synthetic expected native fixture.
Full native v089259 и real model status/quality pending.

## Первый Mac запуск

[Процедура](RESEARCH_MAC_V089.ru.md): полный native preflight и один positive
RU Documentation control о Main, cap1, вместо немедленного полного packet.
Используется неизменный derived known diagnostic_main_ru_v086.json: точно
тот же scoped вопрос/роль; Git question исключён, Main assembly не вызывается.
Этот control не является complete Main pair или независимым held-out вопросом.
Его required_points не изменены: полнота остаётся отдельным review.
Существующий CURRENT не перестраивать; preflight temporary FTS smoke отделён.

После review: paired unknown для контроля abstention, затем full Main и
serialized/paths/paraphrase/uncertain quality cases. Если status по-прежнему
wrong, raw report сохранить и не replay без новой обоснованной процедуры.

Этап7 открыт: final-version complete known regression, independent held-out/
human review,3paired repeats,E2E/actual changed-files Chain,controlled native
cold/warm/tokens/RAM/swap и research decision. Этап8 только после уведомления
о закрытии7 и согласования с Юрием, когда его начинать.
