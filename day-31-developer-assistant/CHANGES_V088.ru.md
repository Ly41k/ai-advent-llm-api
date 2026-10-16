# v088 / 0.7.18 — полнота вопроса и поддержка каждого тезиса

## Подтверждённый результат v087

Mac Python 3.13.3: 259 tests passed, 59 Python digests match archive/preflight/
freeze. Ollama GET /api/version 0.40.3; Qwen2.5:14b Q4_K_M digest прежний.
Existing CURRENT 44 docs / 405 chunks, index 27519cd6caa346ac87a18639932506b5
проверен и не заменён. Metadata/admission не выполняют генерацию/embeddings.

Пройдены шесть targeted topic packets: unknown, Main, serialized, paths,
paraphrase, uncertain. 12 известных вопросов из 22, 24 ответа, 32 known Qwen
calls: 28661 input / 2301 output tokens. Technical failures, unknown inference,
model retries, cloud fallback, embedding calls — 0. Отдельный production RU
unknown control: 1 call, 992 input / 24 output. Всего 33 calls, 29653 input /
2325 output. Это один paired repeat и отдельный control, не три repeats.
Остальные 10 вопросов known catalog на v087 не запускались. Это не полная
final-version regression, не held-out, не E2E и не controlled resource benchmark.

33 exact model inputs независимо реконструированы: context/message/schema/
budget SHA совпали. Multi Main получает полный вопрос, проверенные claim texts
и app-created Git facts, без source quotes; его ID-only output сохраняет IDs.
Reported final freshness/Git reobservation прошли; owned workers reaped.
Source files вне доступного Day31 пакета не читались независимо: для Day30/root
цитат оценка использует exact native quotes и reported native provenance checks.

## Что остаётся по качеству

- Unknown: 4/4 paired empty unknown + production control верны.
- Main: published claims поддержаны; ASCII Main сохранён в обоих RU modes.
  Strict rubric неполная: полный вопрос как вход не назван нигде; ID ordering
  лишь EN Single; app-produced Git input явно лишь EN Single. EN Multi слишком
  краток и не противопоставляет явно original excerpts.
- Serialized: RU Multi не отвергает несколько copies; его concurrency clause
  имеет indirect selected support. EN Multi c2 «one model, not one copy per
  agent» снова cites e1/e3, хотя прямая поддержка в e2.
- Paths: EN Multi добавляет categorical part-of-functionality refinement к
  source «документ может описывать только часть». Core limits/branch верны.
- Paraphrase: оба прямых пункта верны, но FTS5 отсутствует во всех четырёх.
  EN Multi добавляет unrequested no-cloud claim без selected direct e2.
  Оба RU modes объединяют два пункта в одном claim. EN source hint=false не
  означает invented citation: Day30 README действительно поддерживает core.
- Uncertain: оба EN-ответа полные; RU Single пропускает explicit no autoreplay.
  RU Multi дублирует uncertain/recovery и fallback facts и добавляет supported
  exclusive-session/before-dispatch details вне вопроса.

Reviews выполнены Codex и не заменяют independent human acceptance.
Все 31 исходных native JSON сохранены byte-for-byte в reports/mac-v087,
reviews/series summary отдельно. Ни один raw ответ не переписан в PASS.

## Изменение v088

Shared SOURCE_RULES RU/EN требуют отдельный claim на пункт вопроса, независимый
повторный выбор supporting IDs для каждого тезиса, поддержку всего текста и
отсутствие дублей/лишнего. Сравнение X/Y должно назвать оба варианта и отвергнуть
неверный. Возможность, отрицание и границы источника нельзя усиливать.
Для component question указаны все относящиеся входы/действия/запреты; для
mechanism question — технология и пределы. Перед JSON — проверка всех пунктов
и их поддержки. Это общие инструкции без fixture IDs, paths, facts/answers.

Первые два правила RU/EN из v087 сохранены точно: support-first empty unknown
и язык/точные имена. RU 1152 bytes / EN 812 bytes. Общие правила одинаковы для
Production Documentation и benchmark-only Single. Новые version pins:
project-answers-v13 / snapshot-single-v14. Main ID-only prompt/code неизменны.

DOC schema status-claims-source-prefix-v6, json-safe-source-prefix-v3, source
ASCII prefix bounds, unsupported_identifier и cited-ascii-name-script-v1
не изменены. Retrieval, Qwen options, context budget, roles, lifecycle/lease
и all eight indexed docs byte-identical. No citation append, text rewriting,
automatic retry/recovery, silent cloud fallback or hardcoded golden selection.
Known v077 catalog/rubric SHA неизменны. Индекс перестраивать не нужно.

Это новый кандидат инструкций; он не даёт программного доказательства entailment
и не принят по семантике до новых native ответов/independent review. Пропуски
v087 не закрываются фактом изменения prompt.

## Offline verification

82 affected tests passed (synthetic model transport). 176 exact historical
input contexts: max8158/8192, без truncation. Новый fixture содержит 33 native
v087 input contexts, включая отдельный diagnostic; это только input/budget
regression, без answer targets и без held-out статуса. Labels не входят в prompts.
44 historical decoded frames проходят independent JSON Schema; app accepts43
и сохраняет rejection старого Мain counterexample. Это format, не semantic PASS.
17 bounded helper/source-guard/real zero-model plan checks прошли с явно
synthetic native-report fixture. Full native v088 259 и real quality pending.

## Следующий шаг и остаток плана

[Mac](RESEARCH_MAC_V088.ru.md): полный native preflight, один production RU
negative control, cap1. При корректном empty unknown: отдельный paired unknown,
затем Main и другие открытые citation/coverage cases. Не запускать packets
автоматически циклом и не повторять existing completed calls.

После подтверждения final version: полная known regression, независимые
held-out вопросы и human review, три paired repeats, E2E (включая настоящий
changed-files Chain), controlled cold/warm/tokens/RAM/swap на Mac, research
decision. Этап 7 открыт. После его закрытия уведомить Юрия и согласовать,
когда начинать этап 8; автоматически этап 8 не запускать.
