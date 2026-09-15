[English](README.md) | **Русский**

# День 11 — явная модель памяти агента

В одиннадцатом задании Бублик разделяет память на три слоя. Каждый слой имеет отдельное назначение, срок жизни и место хранения. Агент не пытается автоматически угадать, что считать важным: место сохранения выбирается явным вызовом метода или CLI-командой.

## Модель памяти

| Слой | Что хранится | Область видимости | Хранилище | Как попадает в prompt |
|---|---|---|---|---|
| Short-term | Последние сообщения текущего диалога | Один диалог | `short_term_messages` | Последние 6 сообщений с исходными ролями |
| Working | `TaskContext` и заметки текущей задачи | Один диалог | `working_memory`, `working_notes` | Отдельный system-блок текущей задачи |
| Long-term | Профиль, решения и знания | Все диалоги | `config/profile.json`, `long_term_memory` | Отдельные system-блоки перед рабочей памятью |

Полная история short-term остаётся в SQLite, но в модель отправляются только последние 6 завершённых сообщений. `pending` и `failed` запросы в prompt не попадают.

## Явный выбор места сохранения

В коде нет общего автоматического классификатора:

- сообщения сохраняются через `start_user_request()` и `complete_exchange()` в short-term;
- текущая задача — через `save_task_context()` в working memory;
- временные данные задачи — через `remember_working()`;
- устойчивое решение или знание — через `remember_long_term(kind, key, value)`.

В CLI это видно напрямую:

```text
/remember working "cargo_limit" "100 единиц"
/remember long decision "engine" "ионный двигатель"
/remember long knowledge "K-41" "на планете обнаружена вода"
```

Working-запись доступна только в выбранном диалоге. Long-term запись появится и в новых диалогах.

## TaskContext и state machine

Рабочая память содержит:

```python
TaskContext(
    task,
    state,
    step,
    plan,
    done,
    current,
    validation_passed,
    validation_details,
)
```

`total` вычисляется как `len(plan)`, поэтому не может разойтись с планом.

Разрешённые переходы:

```text
planning -> execution
execution -> validation | planning
validation -> done | execution
done -> нет переходов
```

Переходы выполняет `TaskStateMachine`, а не LLM. Нельзя начать `execution` без плана, перейти к `validation` с незавершёнными шагами или перейти в `done` без успешной проверки.

Пример полного цикла:

```text
/task create "Создать модуль навигации"
/task plan "Собрать требования" "Написать код" "Запустить тесты"
/task transition execution
/task complete
/task complete
/task complete
/task transition validation
/task check pass "Тесты пройдены, план выполнен"
/task transition done
/task status
```

## Формирование prompt

Перед каждым запросом `MemoryPromptBuilder` собирает контекст в фиксированном порядке:

```text
profile + invariants
long-term decisions and knowledge
working TaskContext and notes
last 6 short-term messages
current user request
```

Команда `/context` показывает точный prompt без отправки запроса в Groq. Так можно проверить, какие данные попали в каждый слой и что действительно увидит модель.

## Invariants и статус ответа

`config/invariants.json` содержит stack, архитектурные ограничения и формализованные правила ответа. Архитектура и stack добавляются в system prompt. Правила с `forbidden_patterns` проверяются обычным Python-кодом после ответа модели.

Если ответ пуст или содержит секрет, он получает статус `FAILED`, не показывается пользователю и не попадает в завершённую short-term память. После успешного ответа CLI показывает:

```text
Memory: short=2, working=2, long=3
Invariants: PASS; checked=empty_response, no_secrets, no_fake_memory
Task: state=planning, progress=0/3, current=—
```

Детерминированная проверка подтверждает только формализованные правила ответа. Соблюдение архитектуры созданных файлов и прохождение тестов фиксируется отдельно командой `/task check` на этапе `validation`.

## Структура

```text
day-11-memory-layers/
├── config/
│   ├── profile.json
│   └── invariants.json
├── agent.py
├── configuration.py
├── experiment.py
├── main.py
├── memory.py
├── models.py
├── prompt_builder.py
├── state_machine.py
├── validators.py
├── test_memory_layers.py
├── README.md
└── README.ru.md
```

Рабочая база создаётся в `data/bublik-memory.db`. Все `*.db`, `*.db-shm` и `*.db-wal` уже исключены из Git.

## Запуск

```bash
pip install -r requirements.txt
python day-11-memory-layers/main.py
```

Основные команды:

- `/memory short|working|long` — показать выбранный слой;
- `/context` — показать собранный prompt;
- `/history` — показать полный завершённый журнал диалога;
- `/remember working KEY VALUE` — сохранить временную информацию задачи;
- `/remember long decision|knowledge KEY VALUE` — сохранить долговременную запись;
- `/task ...` — управлять задачей и её состоянием;
- `/dialogs` — сменить диалог;
- `/exit` — завершить программу.

Значения с пробелами нужно заключать в кавычки.

## Проверка влияния памяти

Автоматические тесты не обращаются к Groq:

```bash
python -m unittest discover -s day-11-memory-layers -p "test_*.py" -v
```

Они проверяют:

- short-term содержит только последние сообщения выбранного диалога;
- working memory изолирована между диалогами;
- long-term memory доступна в новом диалоге;
- все три слоя присутствуют в prompt;
- state machine запрещает некорректные переходы;
- заполненная память изменяет отправляемый модели prompt;
- ответ, нарушающий invariant, отклоняется.

Для сравнения реальных ответов:

```bash
python day-11-memory-layers/experiment.py
```

Эксперимент задаёт один вопрос дважды: без рабочей и долговременной памяти, затем с текущим сигналом о воде в K-41, планом задачи и долговременным приоритетом миссии. Второй ответ должен использовать эти данные и оставаться на этапе `planning`.

## Результат

Бублик получил явную модель памяти: текущий диалог, состояние задачи и устойчивые знания больше не смешиваются. Видимость каждого слоя можно проверить, место сохранения выбирается явно, state machine не позволяет перескакивать через этапы, а результат ответа проходит проверку формализованных invariants.
