# v0.7.14 / v084 — правила полноты и сохранение технических имён

Полный known regression v083 собран: 22 вопроса RU/EN, 44 ответа Single/Multi,
54 Qwen calls, 51006 input / 3996 output tokens. Technical failures, retries,
unknown inference и embeddings — 0. Native v083 252 tests/59 Python SHA passed.
Это одна итерация известных вопросов, не held-out, три repeats или end-to-end.
Сводка и неизменённые raw JSON: `reports/mac-v083-complete/`.

Открытые результаты v083:
- Untracked RU Multi дублирует одну фразу; uncertain RU Multi повторяет запрет fallback разными формулировками.
- Serialized/uncertain Single не называют отвергнутый вариант; serialized Multi не цитируют e2 для запрета копий.
- Main отвечает по сути верно, но не раскрывает все детали закреплённой рубрики: полный вопрос, Git-факты как вход и выбор/порядок IDs.
- Paraphrase правильно даёт два отрицательных ответа, но пропускает FTS5 из рубрики. EN цитирует релевантные Day30/root документы, поэтому designated-source hint=false; это не выдуманные цитаты.
- RU Single использует Мain с кириллическим М.

v084 меняет общие инструкции Documentation/Single, без названий кейсов, путей golden sources или готовых ответов:
один тезис на claim, без перекрытия; обе альтернативы сравнения; нужные входы,
действия и запреты компонента; технология и границы механизма; точное написание имён.
Baseline сначала отвечает на documentation_question, затем выбирает Git IDs.
Schema `status-claims-evidence-first-v5` задаёт evidence_ids перед text для claim.
Математический набор структурных полей, language/status branches, max5 claims,
max3 IDs и bounded safe text patterns не расширены. Порядок schema не доказывает entailment.
Prompt `project-answers-v9`; benchmark Single `snapshot-single-v10`.

Новый application check `cited-ascii-name-script-v1` отклоняет смешанный Latin/Russian
токен, который после ограниченной замены похожих букв совпадает с ASCII-именем в
цитируемом evidence. Например Мain вместо Main. Ответ не переписывается, автоматического
retry нет; завершённый HTTP reply остаётся известным вызовом и закрывает lease.
Это ограниченная проверка написания, не общий Unicode validator, не запрет чистой
транслитерации и не semantic verifier. Claim text по-прежнему начинается с русской
буквы в RU, поэтому инструкция требует русское вводное слово перед ASCII-именем.
Main не получает excerpts и не переписывает Documentation; его ID-only контракт прежний.

Retrieval, corpus (44/405), model/options, lease, no-replay и pair protocol прежние.
59 Python-файлов сохранены. Catalog v077 byte SHA прежний. Индекс не пересобирать.
Нет автоматической дедупликации/добавления фактов/citations или semantic PASS.

Локально: исходные 41 affected tests прошли; после добавления 54-input fixture —
ещё 39 budget/boundary/rejection/research checks. Начальный report сохранён отдельно,
followup pin соответствует финальным Python SHA. 94 входа (40 исторических+54 точных
native v083) укладываются без изменения evidence: max 8163/8192. Independent JSON
Schema принимает 44 старых decoded frames; app check намеренно отклоняет ровно
один с Мain. Это не приёмка качества остальных 43 старых ответов.
16 shell flow/source-guard checks passed со synthetic fixture, никаких настоящих
Mac/Ollama операций здесь не было. Полный native 256-test suite и Qwen v084 pending.

## Установка и первый ограниченный прогон на Mac

Из корня repo, активное установленное окружение Python 3.13:

```bash
unzip -o ~/Downloads/day31-stage7-v084.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v084_mac.sh
```

Ожидается 0.7.14. unzip объединяет содержимое папок; не заменять scripts целиком
через Finder. Полный архив содержит все 59 Python, включая 10 scripts/*.py.
Зависимости прежние; bge-m3/CURRENT индекс не перестраивается. Preflight проверяет
256 tests и настоящий временный FTS/Git/worker smoke без генерации, затем admission,
GET /api/version и source guard. Временный FTS smoke не заменяет существующий CURRENT.
Все семь output filenames проверяются до model operations, без overwrites.

Первый пакет serialized: 2 вопроса × Single/Multi = 4 наблюдения, до 6 последовательных
Qwen calls, embeddings 0, без warmups/дополнительных probes. Никакой следующий пакет
не запускается автоматически. Day30 и другие Ollama clients выключены как прежде.
Старые freezes не использовать: source/prompt/schema changed; helper создаёт новый paired freeze.
Операторский restart/verified recovery только по прежней процедуре при закрытом gate;
helper не перезапускает Ollama. При stopped не удалять отчёты и не повторять запуск.

После возвращения prompt терминала прислать:

```text
/tmp/day31-stage7-preflight-mac-v084.json
/tmp/day31-quality-admission-mac-v084.json
/tmp/day31-ollama-version-mac-v084.json
/tmp/day31-paired-serialized-mac-v084-index-verify.json
/tmp/day31-paired-serialized-mac-v084-plan.json
/tmp/day31-paired-serialized-mac-v084-freeze.json
/tmp/day31-paired-serialized-mac-v084-result.json
```

После review доступны continue_v084_mac.sh unknown/untracked/serialized и
continue_regression_v084_mac.sh receipt/assistant/dense/language/paths/main/paraphrase/uncertain.
Каждый выбирает только один RU/EN пакет, cap4/6 и новый paired freeze, без повторной
полной suite. Не запускать следующий пакет до разбора текущего.

Этап 7 OPEN: нужна реальная проверка нового качества/полная регрессия итоговой версии,
независимые новые вопросы и human review, три paired repeats, current end-to-end,
контролируемые native cold/warm/tokens/RAM/swap и сводный вывод исследования.
После завершения 7 сообщить Юрию и согласовать, когда начинать 8. Этап 8 автоматически не начинать.
