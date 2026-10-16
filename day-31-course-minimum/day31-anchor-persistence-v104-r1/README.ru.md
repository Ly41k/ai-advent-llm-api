# Day 31 / Stage 7 — v104: Source Anchor Persistence + Semantic Acceptance Gate

Статус: локальная реализация и offline-проверка завершены; Stage 7 открыт. Новых генераций Qwen — 0. Полная регрессия не запускалась. Установленное приложение v099, исходный helper v103 и результаты v103 не менялись.

## Исходный дефект и изменение

В v103 `source_quote` присутствует в raw-ответе. `source_anchors.select()` уже предоставляет source path, точную цитату, offsets, строки и SHA-256 документа. Повторная модель данных источника не нужна. Однако `validate_anchor_output()` удаляет цитату при нормализации, а `forensic_capture.analyze()` заполняет `source_anchors` только после успешной проверки всего ответа. Поэтому итоговые claims теряют выбранную опору, а отклонённый EN-3 Multi не имеет заполненного списка anchors в analysis.

Новый внешний finalizer использует те же `source_anchors` и добавляет к итоговому result три поля:

- `source_anchors`: существующая структура anchor + `claim_id`, исходный `text`, `claim_sha256`, `in_answer`, `exact_anchor_check`, исходный `runtime_validation` и `binding_sha256`;
- `anchor_binding`: версия политики, fingerprint исходного result/raw/context/frame, request/task IDs и версия результата;
- `semantic_acceptance`: отдельное решение о смысловой поддержке и `answer_accepted`.

`evidence_id` — существующий source ID внутри контекста; `source` — относительный путь; `start_line/end_line` — диапазон строк; `quote` — точный выбранный anchor; `raw_digest/text_digest` — fingerprint документа. Новые алиасы `source_id`, `exact_anchor` и дублирующая сущность source не вводились.

Anchor берётся исключительно по исходным `evidence_ids` и `source_quote` сохранённой claim. Полный pinned document используется прежним v103 механизмом только для проверки границ/происхождения, а не для подбора другого доказательства или смысловой поддержки. Если anchor отсутствует/изменён/не подходит ID, он не заменяется. Запись остаётся непроверенной либо обнаруживается конфликт с исходным runtime result.

Для отклонённого raw сохраняются диагностические anchors с `in_answer=false`; исходный `claims=[]`, fallback answer, отказ и diagnostics остаются неизменными.

## Семантический допуск

| Статус | Основание |
|---|---|
| `supported` | Явный review от настроенного человеком reviewer, весь text размечен, все части отмечены supported с опорами внутри собственной выбранной цитаты. |
| `unsupported` | Явный допустимый отрицательный review установил неподдержанную необходимую часть. В текущем прогоне это сохранённые выводы Codex-аудита; это не результат эвристики. |
| `needs_review` | Нет review, reviewer не разрешён, review устарел/некорректен, есть неоднозначность, anchor не проверен или есть только положительная assistant-оценка. |

Автоматического определения логического следования нет: `automatic_semantic_entailment=false`. Существование цитаты, проверки identifiers и совпадение текста не присваивают supported.

`authorities` передаётся оператором отдельно от review-файла. По умолчанию offline CLI доверяет только идентифицированному assistant-аудиту для отрицательных выводов; он не создаёт human approval. Явное положительное решение человека применяется через `semantic_gate(record, review, authorities={reviewer_id: 'human'})` или `attach(...)`. Это локальная конфигурация доверия, а не криптографическая аутентификация личности или доказательство независимости оценщика.

Review привязан одновременно к policy/result version, fingerprint полного исходного result и raw/context/frame, тексту claim, её ID, конкретной цитате, source path/ID, spans/строкам и документным digest. Изменённый ответ, другой anchor, другая версия или перенос решения между claims делает старое решение неприменимым. Поддержка каждой части review должна находиться внутри ЕЁ anchor. Разметка должна покрывать весь исходный текст без пропусков или перестановки. Для составной claim любая unsupported часть даёт unsupported всей claim.

`answer_accepted=true` возможно только при исходном runtime pass И supported всех claims. Ни review человека, ни assistant-review не могут превратить исходный runtime rejection в принятый ответ. Полнота/расширенная рубрика учитываются отдельно от grounding. Этот gate не объявляет Stage 7 завершённым.

## Offline-результат сохранённых v103

| Ответ | Runtime v103 | Review findings по claims | Статус gate | Итог |
|---|---|---|---|---|
| RU-1 Single | passed | c1 supported; c2 supported | needs_review | Grounding не отклонён; требуется явное human review. Пропуск расширенного причинного объяснения — отдельно в completeness. |
| RU-1 Multi | passed | c1 supported; c2 supported | needs_review | То же. |
| EN-3 Single | passed | c1 supported; c2 unsupported | unsupported | Read-back equality в c2 отсутствует в её выбранной цитате; answer_accepted=false. Наличие подходящей информации в другом фрагменте e1 не используется. |
| EN-3 Multi | rejected / unsupported_identifier | c1 unsupported; c2 unsupported | unsupported | Исходный отказ сохранён; обе raw claims остаются только диагностикой, in_answer=false. |

Для RU-1 `needs_review` не означает ошибку grounding: у всех четырёх claims положительные сохранённые assistant findings. Отсутствующее защитное объяснение о прерванном/неуспешном обмене не превращено в unsupported. Для EN-3 Single первая claim правильно сопоставляет HTTP400 tool_use_failed → fallback, premature choice → correction и исключает оба шага из model-selected.

EN-3 Multi остаётся проблемой генерации: c1 смешивает происхождение выбора операции с проверкой результата и вводит метки вне своей цитаты; c2 вводит verified=true вне собственной цитаты. Новый gate фиксирует и блокирует эти дефекты, но не исправляет текст модели. Представимость корректного ответа в схеме не засчитывается как успешная генерация.

## Подключение к pipeline и совместимость

`pipeline_adapter.AnchorSnapshotPipeline` — opt-in subclass существующего `SnapshotPipeline`. Он вызывает прежний pipeline один раз, затем связывает результат с уже записанным raw capture и сохраняет расширенный итоговый envelope в отдельном приватном `anchor_report_dir` через прежний атомарный exclusive writer. Оригинальные raw, trace и journal не переписываются. Повторная запись идентичного финального envelope не создаёт дублей; конфликт не перезаписывается.

Адаптер намеренно ограничен v103 Documentation/Single экспериментом с одним captured model task. Его применение к Chain или multi-call Fan-Out требует отдельной проверки; скрытого обобщения нет. Нормализованные claims, citations, модельные сообщения, schema, параметры, retrieval, бюджеты и метрики не изменены.

Приложение `main.py` и существующий v103 runner не заменены этим пакетом. Для следующего отдельно согласованного live-пакета нужно явно выбрать новый adapter вместо SnapshotPipeline. Consumers расширенного результата должны проверять `semantic_acceptance.answer_accepted`, а не считать runtime completed семантической приёмкой. Историческое поле answer сохранено для совместимости/аудита. `verify_envelope(...)` проверяет целостность результата и воспроизводимость gate перед сохранением/использованием; исходное `semantic_support_verified=false` сохранено.

Новый offline JSON bundle сохраняет прежний `day31-evidence-bundle-v1`: все 24 старых файла и их хеши остаются точь-в-точь прежними; добавлены только `day31-v104-anchor-acceptance.json` и `day31-v104-bound-review-decisions.json`. Старый result не заменён новым.

## Файлы реализации

- `anchor_acceptance.py`: сохранение anchors, проверка bindings, семантический gate, additive attach и проверка финального envelope.
- `pipeline_adapter.py`: подключение к финалу существующего pipeline и отдельное атомарное сохранение итогового результата.
- `offline_audit.py`: offline CLI для исходных четырёх ответов; создание нового совместимого bundle без вызовов модели.
- `test_acceptance.py`, `run_tests.py`: целевые локальные тесты и runner с запретом сети.
- `inputs/`, `input-pins.json`: неизменённые native bundle и предыдущая clause-разметка, привязанные хешами.
- `reports/`: новый offline bundle, отчёт тестов и подтверждение неизменности.

Все эти файлы новые. В v099, v103 и днях 1–30 изменений нет.

## Локальные тесты

40 тестов PASS на Linux / Python 3.12.14, 0.739 s. Сетевые соединения заблокированы; Qwen calls=0; failures=0; errors=0; unraisable errors=0.

Проверены разные anchors нескольких claims; составная claim; точные строки/offsets; неправильная цитата в правильном документе; заимствование чужой опоры; отсутствующий/изменённый anchor; неверный evidence ID; изменение ответа/версии после review; устаревший/неполный/дублирующий review; запрет самоназначения assistant человеком; неподтверждённые reviewer; исходный отказ и старые identifier guards; отсутствие автопринятия; additive совместимость старых полей; детерминированный повторный аудит; финальная persistence/idempotence/no overwrite; fingerprint исходных helper/app файлов; запрет изменения gate после review; запрет повторной миграции прежней clause-оценки на изменённый result или другую версию.

Тесты review и finalizer используют явно синтетические решения человека/возвращаемый parent result. Нативные сохранённые ответы реальны. Owned model process в этих новых тестах не запускался; Mac/live integration пока не подтверждена.

## Только offline-команды для Mac

Распаковать новый архив отдельно от репозитория; предыдущий `/tmp/day31-source-anchor-v103-r1` должен сохраниться. Из корня repo в существующей venv:

```bash
unzip -n ~/Downloads/day31-anchor-persistence-v104-r1.zip -d /tmp
python /tmp/day31-anchor-persistence-v104-r1/run_tests.py \
  --v103 /tmp/day31-source-anchor-v103-r1 \
  --app "$PWD/day-31-developer-assistant" \
  --output /tmp/day31-v104-offline-tests-mac-r1.json
python /tmp/day31-anchor-persistence-v104-r1/offline_audit.py \
  --v103 /tmp/day31-source-anchor-v103-r1 \
  --app "$PWD/day-31-developer-assistant" \
  --output-dir /tmp/day31-v104-offline-mac-r1-work
```

Ни одна из этих команд не вызывает Qwen/Ollama. Существующий test-report не перезаписывается. Повторный audit создаёт новый bundle-0002 и сохраняет bundle-0001.

## Возможные регрессии и ограничения

1. Положительные ответы по умолчанию будут needs_review до явного решения человека. Это намеренный допуск приёмки, а не объявление grounded ответов ошибочными.
2. Любое изменение результата/trace/version аннулирует старое review даже при похожем тексте. Повторное использование решений ограничено в пользу целостности.
3. Дополнительная persistence может завершиться ошибкой прав/места/конфликта. Старый raw/trace сохранён; автоматического повторного inference нет. Финальное сохранение нельзя считать успешным при такой ошибке.
4. Старые consumers могут игнорировать новые поля. До подключения adapter и gate к месту публикации `/help` нельзя заявлять production enforcement.
5. Semantic review может ошибиться. Проверки подстрок подтверждают целостность review, а не истинность рассуждения; нужна реальная человеческая оценка. Независимость reviewer не доказана технической конфигурацией доверия.
6. Поддержка Chain/multi-call контекстов ещё не реализована. Полнота RU-1 и расширенный failure-stop пункт EN-3 остаются отдельными замечаниями; качество EN-3 Multi не исправлено.

## Минимальный следующий live-прогон — только после отдельного согласования

Предлагаются максимум 2 последовательных вызова: один EN-3 Single и один EN-3 Multi. Разные worker/normalization пути требуют проверки обоих; повторять RU-1 или всю регрессию для проверки этого изменения не нужно. Промпт, schema, вопросы, evidence selection, модель/параметры и index остаются прежними. Новый run и его артефакты должны быть изолированы от v103; перед запуском фиксируется новая версия adapter/gate.

Цель — проверить путь реальный captured worker → выбранный anchor → final envelope → новый bundle и fail-closed семантический допуск. Улучшение самого ответа не ожидается и не является основанием для повторов до PASS. Старый EN-3 Multi не перегенерируется внутри v103 и остаётся отклонённым независимо от новых наблюдений. На uncertainty или технической ошибке остановка; без автоматического retry. Новый ответ без явного review остаётся needs_review; лексический pass сам по себе ничего не принимает.

Этот live-пакет сейчас не запущен и не включён в команды. После текущих локальных тестов работа остановлена для отдельного согласования запуска. Stage 8 не начинается.
