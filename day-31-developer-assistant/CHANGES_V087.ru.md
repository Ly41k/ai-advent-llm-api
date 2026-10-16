# v087 / 0.7.17 — правила поддержки v085 вместе с форматом v086

## Что показал Mac v086

259 native tests прошли на Python 3.13.3; 59 Python SHA совпали. Existing CURRENT
44 docs / 405 chunks, index 27519cd6caa346ac87a18639932506b5 проверен и не изменён.
Ollama GET /api/version: 0.40.3. Admission: 6/6, zero generation/embedding calls.

Один production Documentation control о Main завершён: 1194 input / 131 output
tokens. Точный вопрос и все три цитаты совпали с rejected v085 role input.
Оба claims начинаются ASCII Main, поддержаны выбранной e1, точно отвечают на
два прямых вопроса. Строгая неизменная рубрика остаётся неполной: не названы
полный вопрос на входе и разрешённое упорядочивание существующих claim/fact IDs.
Main assembly, Git question и Single/Multi pair этот control не проверяет.

Затем первый RU Multi отрицательного packet остановлен: unsupported_identifier.
Один завершённый Qwen call: 993 input / 88 output tokens; HTTP /api/chat success,
conditions после запроса проверены, final provenance passed, worker reaped.
Это тот же sealed input context, что успешно дал empty unknown в v085.
Модельный текст отклонён, claims/citations не опубликованы. Exact unsupported
token неизвестен: raw rejected reply не сохраняется. Нельзя утверждать, что
модель выдумала значения параметров, или называть конкретный token по догадке.

Остальные три наблюдения не запущены; complete pairs 0. Pair flag
conditions_valid_after=false остался initial flag незавершённой пары; request
flag=true. Это не model_epoch_changed. Всего v086: 2 known calls, 2187 input /
219 output tokens, 1 successful Doc control и 1 rejected paired observation.
Ноль model retries, unknown inference, cloud fallback и embedding calls.
Reports сохранены byte-for-byte в reports/mac-v086, reviews отдельно.

## Ограниченное изменение

Schema status-claims-source-prefix-v6 и text policy json-safe-source-prefix-v3
из v086 сохранены byte-for-byte. Prefixes по-прежнему только из цитат, максимум
32 имён / 32 символа, общая длина claim 600. Exact source ASCII prefix разрешён
в начале RU claim перед русской прозой. Это не доказательство смысловой поддержки.

Общие SOURCE_RULES_EN восстановлены точно из v085. SOURCE_RULES_RU восстановлены
из v085, кроме одной строки о языке: старое «с русского слова» заменено строкой
v086 о точных ASCII именах, включая начало text. Таким образом не возвращаем
старый форматный конфликт. Особенно сохранено правило: без поддержки empty
unknown; не описывать отсутствие и не повторять неподтверждённые имена даже
в отказе. RU 1157 bytes / EN 790 bytes. Prompt project-answers-v12,
benchmark-only Baseline snapshot-single-v13; одинаковые общие правила обоих modes.

Это кандидат для проверки, не доказанный semantic fix. v085 прошёл известные
negative controls при другом schema; v087 сочетает прежние инструкции с новым
schema. Native one-call control первым проверит это сочетание. Не меняются
unsupported_identifier, cited-ascii-name-script-v1, validators, Main ID-only
contract, roles, retrieval, Qwen options, token budget или lease. Нет answer
rewriting, auto unknown downgrade, citation append, grammar weakening/retry,
hardcoded case IDs/answers/paths в production prompts. Known v077 catalog и
его required_points неизменны. Held-out acceptance по ним не заявляется.

## Проверки v087

82 affected local tests passed; модельный transport в них synthetic.
143 точных исторических входов: максимум 8163/8192 без обрезки evidence.
Independent JSON Schema: 44 historical frames valid; application принимает
43, старый Мain counterexample отклонён spelling guard. Это format checks,
не semantic PASS 43 ответов. Native v086 Main output также валиден при
неизменной schema/validator v087; это не новый native v087 ответ.
17 shell/source guard/real zero-model CLI plan checks прошли с явно synthetic
native-report fixture. Native full 259 tests и реальные ответы v087 pending.

## Следующий запуск и этапы

[Mac procedure](RESEARCH_MAC_V087.ru.md): полный native preflight, затем один
production RU negative control, cap1. Без пересборки CURRENT/bge-m3; временный
FTS index offline smoke отделён от CURRENT. Никакого auto continuation.
Старый failed packet v086 не повторять; файлы не удалять и не превращать в PASS.
Этот завершённый rejection сам по себе не требует restart/recovery.

После review: v087 paired unknown, затем полный Main packet и открытые
serialized/paths/paraphrase/uncertain citation/coverage cases. На final version
остаются полная known regression, независимый held-out/human review, три paired
repeats, E2E, controlled cold/warm/tokens/RAM/swap на Mac и research decision.
Этап 7 открыт. Этап 8 только после уведомления о закрытии 7 и согласования с Юрием.
