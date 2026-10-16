# v098 / 0.7.28 — объединять совпадающий смысл до записи claims

## Проверенные результаты v097

На Mac прошли 262 теста, 59 Python SHA совпали с выпуском. CURRENT прежний:
44 документа / 405 чанков. Известная RU/EN серия полностью выполнена: 22 вопроса,
44 ответа Single/Multi, 54 вызова, 50470 input / 3905 output tokens.
С отдельным EN uncertain control: 55 вызовов, 51565 / 3982 tokens.
Технических ошибок, model retry, unknown inference attempts и embeddings нет.
Схемы, точные контексты/сообщения, бюджеты и Git/Main ID contracts проверены.
Это один paired repeat на общих FTS/Git snapshots, не production E2E/held-out.

Основные прямые ответы верны; четыре unknown корректно отказались от выдуманных
параметров. Это не общий quality PASS. Два RU Multi ответа повторяют смысл:

- uncertain: recovery повторяется, затем повторён запрет cloud fallback;
  дополнительный pre-dispatch факт при этом поддержан источником;
- untracked: одна политика чтения дважды пересказана по RU и EN цитатам.

В RU uncertain появился фрагмент «No автоматического cloud fallback нет».
Source-prefix guard допускает capitalized ASCII слово No, которое есть в цитате.
Этот guard не распознаёт имена собственные и не гарантирует естественный язык.
Прежняя EN uncertain двусмысленность запрета/recovery не воспроизвелась.
FTS5, exact relative-path mechanism, full-question/ID details Main и другие
расширенные пункты rubric явно раскрыты не везде. Исходные rubrics сохранены;
семантически правильный выбор альтернативы не требует дублирующего отрицания.

Все 51 исходный JSON, 12 оригинальных bundles и 12 отдельных reviews сохранены
без изменений в reports/mac-v097. Общая сводка там же включает 55 точных модельных
входов. Это input regression, не золотые ответы. Итоговая сводка не заменяет
исходные semantic_acceptance=not_evaluated на PASS. Независимый human review pending.

## Изменение v098

В shared SOURCE_RULES добавлен порядок составления: объединить одинаковый факт
из цитат разных языков до записи и сослаться на их IDs в одном claim. Следующий
claim должен добавлять новый смысл; иначе остановиться. Это уточняет прежнее
«факт один раз» применительно к нескольким источникам, не удаляя evidence.
Для RU явно указано переводить служебные слова, сохраняя ASCII имена/API.
Нет примеров с No, названий кейсов, source paths или готовых фактов в правилах.
Поддержка источниками, прямой ответ всем частям, отрицания/условия и status rules
сохранены; английская языковая строка прежняя, русская уточнена.
Rules: EN776 bytes (−13), RU1108 (+13). Prompt project-answers-v22;
Single snapshot-single-v23. Одинаковые shared rules используются обоими режимами.

Схема text-first-v7, source-prefix pattern, identifier guards, transport и runtime
остались прежними. В частности, плохой prefix No по-прежнему структурно допустим:
ожидаемый эффект проверяем на реальной модели, не выдаём prompt за verifier.
Нет удаления дублей после генерации, скрытой правки текста, append citations,
status promotion, дополнительного LLM verifier или новых model calls.
Router, corpus, retrieval, Main ID-only, options, lease и retry policy не изменены.
Это ограниченный кандидат; исправление повторов/языка пока не доказано.

## Локальная проверка и Mac

88 affected tests прошли на Python3.12 с синтетическим transport. Все 436 точных
контекстов укладываются в текущую budget policy: максимум8182/8192, evidence и
вопросы не сокращены. Это estimate UTF-8+allowances/reserves, не точный tokenizer.
17 helper checks и 13 invariant/schema/bundle checks прошли. Все44 native v097
frames остаются структурно допустимыми, включая повторы и No: это подтверждает
сохранение контракта, а не качество. Первоначальный локальный запуск без нужного
PYTHONPATH не нашёл установленный jsonschema; failed report сохранён отдельно.
После подключения существующей зависимости все88 прошли без правки кода.
Native v098262 и semantic effect pending.

Первый Mac helper выполняет новый262-test preflight, CURRENT verify, admission,
GET Ollama version, source59/catalog/diagnostic-plan guards и fresh freeze.
Затем только один RU uncertain Documentation control, generation cap1/embeddings0.
Это тот же scoped вопрос, что RU Multi v097; actual retrieval проверим по новому
report. Нет Main/Git generation и auto-next packet. Preflight FTS smoke использует
отдельный temporary index/model0/emb0; CURRENT не заменяется.
Один bundle сохраняет7 исходных JSON+SHA; stopped/partial не переписываются в PASS,
исходный ненулевой exit code сохраняется. [Запуск](RESEARCH_MAC_V098.ru.md).

## До закрытия этапа 7

- Оценить/исправить повторы, язык, grounding и полноту на итоговой версии;
  затем выполнить её полную известную regression.
- Независимые held-out вопросы и human semantic review.
- Три paired repeats на зафиксированной итоговой версии.
- Production E2E, включая actual changed-files Chain.
- Контролируемые native cold/warm, tokens, RAM/swap и research decision.

Этап7 OPEN. После закрытия сообщить Юрию и согласовать время начала8;
автоматически этап8 не начинать.
