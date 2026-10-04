# Полная проверка v7: обе модели qwen2.5:14b

**Задание пока не закрыто: вручную подтверждены 5/10 положительных ответов; автоматический отчёт показывает 6/10. Оба отрицательных контроля прошли.**

Проверен присланный evaluate_v7_both14b.json. Протокол quote-ids-repair-v7, generator/verifier qwen2.5:14b, fixed / candidate_k=20 / final_k=5 / cosine=0.50 / heuristic. Модель запускал пользователь; ассистент выполнил последующую сверку. Этот разбор не является независимой человеческой оценкой.

Все 16 опубликованных цитат дословны и совпадают со своими чанками, файлами, номерами строк и привязкой к claim/source. Также проверены 898 фрагментов каталога, 46 выбранных чанков и локальный контракт 16 draft. Семантическую правильность такие механические проверки сами по себе не доказывают.

Оригинальный JSON сохранён побайтно. В reviewed сохранены исходные summary, model results, checks и contract_pass; добавлены только manual_review, manual_summary и сведения о сверке. Программный код v7 в этом разборе не менялся.

## Каждый нюанс задания

| Требование | Проверенный результат |
|---|---|
| Ответ на 10 вопросов с доступной информацией | 6 опубликованных ответов, 4 unknown; полностью подтверждены 5/10 |
| Источники: source + section/chunk_id | Есть во всех 6 опубликованных ответах, метаданные совпадают с retrieval |
| Цитаты из найденных чанков | Есть во всех 6 ответах; 16/16 дословны |
| Смысл ответа соответствует цитатам | Факты всех 6 опубликованных ответов поддержаны; №10 неполон по запросу |
| Не знаю при релевантности ниже порога | negative-02: below_threshold, 0 выбранных чанков, 0 model calls |
| Просьба уточнить при отказе | Есть во всех 6 unknown, включая оба отрицательных контроля |
| Не выдумывать при недостаточном содержании | negative-01: 1 чанк выше порога, затем unknown/insufficient_context |
| Повторная проверка | Выполнена для всех 12 случаев; ложный отказ №7 и ошибочная полнота №10 выявлены |

Отказ не содержит фиктивных источников и цитат. На положительных вопросах unknown не засчитывается как правильный содержательный ответ.

## Результаты 10 вопросов и примеры ожидаемых ответов

Примеры ниже написаны ассистентом для ручной проверки по уже найденным источникам. Они не являются полученными ответами модели и не передаются production-агенту. Quote IDs относятся только к этому отчёту и могут меняться в другом retrieval.

### positive-01: How are multiple Bublik dialogues isolated and restored after restart?

Unknown. Цитата q2_23 прямо содержит UUID и выбор сообщений по conversation_id, но ответ не объясняет эту границу, а SQLite/restoration не подтверждены выбранными q2_24–26. q2_3 с загрузкой выбранной истории есть в retrieval, но не выбран. Repair меняет формулировку, сохраняя те же четыре citations. В первом verdict также ошибочно отрицается явно описанная в q2_23 изоляция.

**Пример ожидаемого ответа:** Каждая тема получает UUID; в запрос LLM включаются только сообщения выбранного conversation_id. История хранится в SQLite и загружается при выборе прежнего диалога после перезапуска.

**Доказательства из этого retrieval:**

- source: `day-07-context-persistence/README.md`; section: `README.md`; chunk_id: `3ed667af5d9b09b484ff`; quote_id: `q2_23`; строки 50–50.

> Every new topic receives a UUID. The same `BublikAgent` class can therefore be reused for any dialogue, while each LLM request receives messages only from the selected `conversation_id`.

- source: `day-07-context-persistence/README.md`; section: `README.md`; chunk_id: `3ed667af5d9b09b484ff`; quote_id: `q2_3`; строки 5–5.

> The seventh assignment adds multiple persistent contexts to the Bublik agent. The user can create a new topic or select a previous dialogue. Its messages are loaded from SQLite and included in the next LLM request.

### positive-02: What stages does Bublik's persistent task state machine use?

PASS. planning, execution, validation, done подтверждены диаграммой q1_5. fail не объявлен состоянием. Дополнительная q1_18 про Continue не нужна для перечня стадий, но не делает его неверным.

**Пример ожидаемого ответа:** Стадии задачи: planning, execution, validation и done. fail обозначает переход при неудачной проверке, а не отдельное состояние.

**Доказательства из этого retrieval:**

- source: `day-13-task-state-machine/README.md`; section: `README.md`; chunk_id: `86c78c2b6743616d18fe`; quote_id: `q1_5`; строки 9–13.

> ```text
> planning → execution → validation → done
>                ↑           |
>                └── fail ───┘
> ```

### positive-03: Where are versioned invariants checked around the model response?

PASS. Локальная и семантическая проверки до генерации и после неё подтверждены диаграммой q1_11; q1_21 уточняет postflight до сохранения. Ответ краткий, но отвечает на вопрос о расположении проверок. Нулевое покрытие ожидаемых слов preflight/postflight является лексической диагностикой, не доказательством ошибки.

**Пример ожидаемого ответа:** До генерации ответа запрос проходит local regex preflight и semantic request guard. Сгенерированный ответ проходит local + semantic postflight перед сохранением; нарушение приводит к отказу.

**Доказательства из этого retrieval:**

- source: `day-14-invariants/README.md`; section: `README.md`; chunk_id: `fb411216a0e054ae9613`; quote_id: `q1_11`; строки 35–47.

> ~~~text
> user request
>     ↓
> local regex preflight
>     ├── conflict → deterministic refusal → SQLite
>     └── pass → semantic request guard
>                    ├── conflict → deterministic refusal → SQLite
>                    └── pass → answer generation
>                                   ↓
>                          local + semantic postflight
>                                   ├── violation → explained refusal → SQLite
>                                   └── pass → answer → SQLite
> ~~~

- source: `day-14-invariants/README.md`; section: `README.md`; chunk_id: `fb411216a0e054ae9613`; quote_id: `q1_21`; строки 75–75.

> The generated response is checked before persistence by both local rules and an independent semantic guard covering every invariant. A violating response is discarded and never stored. Instead of AgentError, the user receives a deterministic refusal with the invariant ID, rationale, and compatible alternative.

### positive-04: Why can execution start only after plan approval, and why can done happen only after successful validation?

PASS. Непустой явно утверждённый план для execution и PASS для done указаны в собственных строках таблиц. Возврат в execution при неудачной validation также дословно подтверждён.

**Пример ожидаемого ответа:** Переход planning → execution требует непустого явно утверждённого плана. validation → done разрешён только при PASS; неудачная проверка возвращает в execution.

**Доказательства из этого retrieval:**

- source: `day-15-controlled-transitions/README.md`; section: `README.md`; chunk_id: `278d64d3279925070457`; quote_id: `q1_8`; строки 11–11.

> | planning | execution | A non-empty, explicitly approved plan is required |

- source: `day-15-controlled-transitions/README.md`; section: `README.md`; chunk_id: `278d64d3279925070457`; quote_id: `q1_10`; строки 13–13.

> | validation | done, execution | `done` requires PASS; failed validation returns to execution |

### positive-05: How does the Day 16 MCP client discover the ping and add tools over stdio?

Unknown. stdio и list_tools подтверждены, но выбранные цитаты не называют ping/add. Их имена есть в q3_13/q2_13 и примерах вывода. Scope правильно отклоняет неполный набор доказательств; repair дословно повторяет draft и citations.

**Пример ожидаемого ответа:** Клиент подключается через stdio_client, создаёт ClientSession и выполняет initialize(). Затем await session.list_tools() получает инструменты сервера; в этом сервере объявлены ping и add.

**Доказательства из этого retrieval:**

- source: `day-16-mcp-connection/client.py`; section: `client.py`; chunk_id: `952d4eeae59bc055afe2`; quote_id: `q1_7`; строки 21–23.

> async with stdio_client(server_params) as (read_stream, write_stream):
>         async with ClientSession(read_stream, write_stream) as session:
>             initialization = await session.initialize()

- source: `day-16-mcp-connection/client.py`; section: `client.py`; chunk_id: `952d4eeae59bc055afe2`; quote_id: `q1_9`; строки 32–32.

> tools_result = await session.list_tools()

- source: `day-16-mcp-connection/README.md`; section: `README.md`; chunk_id: `c5de6cc4dc780aa977f5`; quote_id: `q3_13`; строки 18–18.

> - `server.py` — minimal local MCP server with `ping` and `add` tools.

### positive-06: What is the name of the first GitHub MCP tool Bublik calls on Day 17?

PASS. get_github_repo явно указан в инструкциях Day 17, включая запрос модели и вызов через ClientSession.call_tool. Lesson identity согласована с путями обоих источников.

**Пример ожидаемого ответа:** Инструмент первого GitHub MCP-урока называется get_github_repo(owner, repo).

**Доказательства из этого retrieval:**

- source: `day-17-first-mcp-tool/README.md`; section: `README.md`; chunk_id: `96300ca424f79a71d174`; quote_id: `q1_5`; строки 8–15.

> 1. `server.py` registers `get_github_repo` with `@mcp.tool()`.
> 2. Type annotations and the docstring publish the input JSON Schema and tool
>    description through MCP.
> 3. The agent requests the MCP tool list and gives those schemas to the model.
> 4. The model requests `get_github_repo(owner, repo)`.
> 5. The agent calls the tool through `ClientSession.call_tool()`.
> 6. The MCP server requests repository data from GitHub REST API.
> 7. The result is returned to the model and used in its final answer.

### positive-07: Which process periodically collects GitHub repository snapshots into SQLite on Day 18?

Unknown из-за ложного отказа основного verifier. q3_6 прямо говорит «повторный запуск будет через заданный интервал»; q4_11 вычисляет next_run через interval_minutes. Draft правильно называет worker.py и SQLite, доказательства поддерживают периодический сбор. Повтор не меняет draft. Правильный отклонённый draft не засчитывается как опубликованный ответ.

**Пример ожидаемого ответа:** worker.py берёт просроченные задания, получает метрики GitHub через REST API и сохраняет снимки в SQLite; следующий запуск происходит через заданный интервал.

**Доказательства из этого retrieval:**

- source: `day-18-scheduled-mcp/README.ru.md`; section: `README.ru.md`; chunk_id: `b165333c1d1e56698605`; quote_id: `q3_6`; строки 10–10.

> - `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.

### positive-08: Which three MCP tools form the Day 19 repository fetch, summarize and save pipeline?

PASS. search_repository, summarize_repository и save_report подтверждены вводным абзацем README и собственными определениями в server.py.

**Пример ожидаемого ответа:** Цепочка Day 19: search_repository → summarize_repository → save_report. Они получают метаданные, создают Markdown-сводку и сохраняют её.

**Доказательства из этого retrieval:**

- source: `day-19-mcp-composition/README.md`; section: `README.md`; chunk_id: `dfb3ad7d44874465e0ce`; quote_id: `q1_2`; строки 3–3.

> One command runs three separate MCP tools over stdio: `search_repository(owner, repo)` fetches public GitHub metadata, `summarize_repository(repository)` converts the exact result into Markdown, and `save_report(summary)` writes the exact summary to disk. `BublikPipelineAgent.run()` verifies discovery, calls tools in order, and stops on error. No Groq key or VPS is needed; the summary is deterministic.

### positive-09: How is the Day 20 report flow routed across MCP servers and how is the saved report verified?

Unknown. Порядок пяти операций и сравнение прочитанного отчёта с оригиналом верны. Однако claim говорит о MCP servers, а его единственная q1_3 содержит только маршрут; q1_2 с тремя серверами и registry не выбрана. Scope отклоняет эту привязку. В v6 repair удалил спорную фразу и ответ прошёл, здесь обе попытки дословно совпадают.

**Пример ожидаемого ответа:** Registry обнаруживает инструменты трёх серверов github, analysis и storage и направляет вызовы в нужную сессию. Маршрут: github.get_repository_info → analysis.summarize_repository → storage.save_report → storage.read_report → analysis.verify_report. Проверка сравнивает прочитанный с диска отчёт с исходной сводкой.

**Доказательства из этого retrieval:**

- source: `day-20-mcp-orchestration/README.md`; section: `README.md`; chunk_id: `d51bc9e2de0500131e22`; quote_id: `q1_2`; строки 3–3.

> Bublik launches three independent stdio MCP servers: `github` (`get_repository_info`), `analysis` (`summarize_repository`, `verify_report`), and `storage` (`save_report`, `read_report`). The registry discovers tools and routes each selected call to the correct server session. The model sees short operation codes such as `FETCH` and `READ` and selects one via strict JSON, for example `{"operation":"READ"}`. The agent maps it to the discovered MCP route and supplies exact validated inputs from prior results. Native Groq `tool_calls` and model-generated report arguments are not required. Real input schemas remain available in the registry and are enforced by the servers.

- source: `day-20-mcp-orchestration/README.md`; section: `README.md`; chunk_id: `d51bc9e2de0500131e22`; quote_id: `q1_3`; строки 5–8.

> ```text
> github.get_repository_info → analysis.summarize_repository
> → storage.save_report → storage.read_report → analysis.verify_report → answer
> ```

- source: `day-20-mcp-orchestration/README.md`; section: `README.md`; chunk_id: `d51bc9e2de0500131e22`; quote_id: `q1_4`; строки 10–10.

> The final verification compares the report read from disk with the original summary. Each pending selection uses strict JSON Schema with an enum of operation codes. If Groq returns HTTP 400 `tool_use_failed`, the agent picks the next guarded step and labels it `agent fallback`. If the model selects a premature step, the agent executes the valid next step and labels it `agent correction`. Neither step can be counted as model selected. The agent forms the final answer from verified MCP results without a sixth model request. Invalid JSON and MCP failures stop the flow; the agent only reports success after `verified=true`.

### positive-10: Как на Day 18 проверить, что периодический сбор GitHub-сводки действительно работает на VPS?

Частично. Все четыре команды реальные и дословно процитированы. Но ответ не объясняет наблюдаемые повторные сводки/снимки и не отделяет запуск сервиса от подтверждения периодического сбора. Primary ошибочно объявляет answers_question=true вопреки критерию v7. Отсутствие полноты не означает, что команды выдуманы.

**Пример ожидаемого ответа:** Запустите сервис bublik-day18 и проверьте его через systemctl status; просматривайте journalctl -u bublik-day18 -f. Подтверждением сбора служат повторные агрегированные сводки, которые worker печатает после каждого запуска. Через get_github_summary можно проверить сохранённые снимки и их количество. Одного статуса работающего сервиса недостаточно, чтобы подтвердить повторные сборы.

**Доказательства из этого retrieval:**

- source: `day-18-scheduled-mcp/README.ru.md`; section: `README.ru.md`; chunk_id: `b165333c1d1e56698605`; quote_id: `q3_24`; строки 50–55.

> ```bash
> sudo systemctl daemon-reload
> sudo systemctl enable --now bublik-day18
> sudo systemctl status bublik-day18
> journalctl -u bublik-day18 -f
> ```

- source: `day-18-scheduled-mcp/README.ru.md`; section: `README.ru.md`; chunk_id: `b165333c1d1e56698605`; quote_id: `q3_3`; строки 5–5.

> Бублик через MCP ставит публичный GitHub-репозиторий на периодическое наблюдение. Отдельный worker постоянно проверяет расписание, сохраняет снимки в SQLite и печатает агрегированную сводку в журнал после каждого запуска. Агент по запросу читает сохранённую сводку через MCP и отвечает с её данными.

- source: `day-18-scheduled-mcp/README.ru.md`; section: `README.ru.md`; chunk_id: `b165333c1d1e56698605`; quote_id: `q3_7`; строки 11–11.

> - `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.

## Отрицательные контроли

**negative-01: What was the exact revenue of Bublik Solutions in 2025?**

PASS. Неизвестная точная выручка не выдумана; есть отказ и просьба уточнить. Один чанк прошёл порог, затем генератор вернул unknown: insufficient_context. Это проверка отказа при недостаточном смысле, а не порогового отказа.

Ответ: I don't know: the retrieved context is insufficient for a supported answer.

Уточнение: Please clarify the course day, file, or function you mean.

**negative-02: Как рассчитывается орбита спутника Юпитера?**

PASS. eligible_count=0, selected_count=0, reason=below_threshold, model_calls=[] при cosine-пороге 0.50. Ответ «Не знаю» и уточнение возвращены до генерации и семантических проверок.

Ответ: Не знаю: найденного контекста недостаточно для подтверждённого ответа.

Уточнение: Уточните день курса, файл или функцию, о которых спрашиваете.

## Что установлено для дальнейшей доработки

1. Не снижать порог для исправления этих ошибок: на №1, 5, 7 и 9 нужные сведения уже найдены выше 0.50. На №10 тоже найдены описания повторных сводок и снимков.
2. Разобрать выбор evidence и repair на №1/5/9: модель повторно выбирает прежние неподходящие или неполные citations. Typed feedback v7 это не устранил.
3. Отдельно исправить семантическую оценку №7: она отрицает периодичность вопреки собственной цитате про повтор через заданный интервал. Автоматически обходить отрицательное решение по номеру вопроса нельзя.
4. Отдельно исправить проверку полноты №10: собственные правильные команды ещё не дают объяснения наблюдаемого результата. Проверка фактов и проверка полноты — разные задачи.
5. После следующего изменения сначала проверить №1/5/7/9/10, затем все 10 положительных и оба отрицательных вопроса. Должны пройти и автоматический контракт, и ручная сверка. Новый код на живой модели пока не проверен, поскольку в этом разборе нового кода нет.

В присланном отчёте нет данных о фактическом числе входных токенов Ollama или обрезке prompt. Переполнение контекста, нехватка памяти, quantization и аппаратные ограничения не установлены и не используются как объяснение ошибок.

Полный прогон уже получен; повторять неизменённый evaluate сейчас не требуется. Для чтения отчёта не нужно менять индекс, модели или рабочие файлы проекта.
