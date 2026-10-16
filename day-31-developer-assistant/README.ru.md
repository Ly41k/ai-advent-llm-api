[English](README.md) | **Русский**

# День 31 — Bublik Developer Assistant

Ассистент разработчика отвечает по документации проекта через Project RAG, получает Git-факты через настоящий MCP-сервер и делегирует задачи ролям Documentation, Git и Verification. Генерация выполняется локальной Qwen через Ollama.

**Учебное задание завершено в границах Course Minimum — Accepted.** На Mac подтверждены работа инструментов, делегация, отказ без evidence и один положительный ответ RU-1 / Multi с точными цитатами. Пользователь явно подтвердил обе claims; Publication Gate выдал `answer_accepted=true`. Видео демонстрации записано.

**Расширенный Research Stage 7 не завершён.** Его ограничения и отложенные исследования сохранены в [BACKLOG_AFTER_COURSE.ru.md](BACKLOG_AFTER_COURSE.ru.md). Учебная приёмка не означает общей приёмки качества модели, всех вопросов или полноценного multi-task Chain.

## Проверенная конфигурация

| Компонент | Подтверждённая граница |
|---|---|
| Базовое приложение | App 0.7.29; исходный `main.py` и 60 Python-файлов сохранены |
| Публикация модельного ответа | Изолированная копия приложения с Publication Gate v104-r2, launcher Course Minimum r3 |
| Documentation-сценарий | Зафиксированный RU-1 / Multi, существующий v103 source-anchor producer и selector |
| Project RAG | Отдельный FTS54: 54 документа / 510 чанков; production44: 44 документа / 405 чанков сохранён отдельно |
| Модель | Локальная Qwen2.5:14b Q4_K_M; temperature 0, seed 31, context 8192, output 1024 |
| Генерации согласованного live-прогона | Один реальный вызов Documentation worker, без повторов и cloud fallback |
| Semantic acceptance | Явное human review, привязанное к неизменным claims, выбранным exact anchors и версии результата |

В RU-1 объясняются статусы `pending`, `completed`, `failed` и восстановление истории. Пользователь принял пропуск расширенного защитного причинного объяснения как неблокирующее ограничение полноты. Grounding и полнота оценивались отдельно.

## Архитектура

| Роль | Обязанности |
|---|---|
| Main | Детерминированные routing, общий budget, постановка tasks, merge и итоговая проверка |
| Documentation | Поиск документации в отдельном worker; ограниченный model task по выбранному evidence context |
| Git | Read-only MCP stdio: branch, status, files, diff; без commit/push и произвольного shell |
| Verification | Проверка provenance, источников, точных цитат и формата; не заменяет human semantic review |

`agents demo` запускает отдельные Documentation/Git tasks, затем Verification проверяет результаты и Main объединяет их. Это реальные процессы и MCP/FTS, без генерации. В принятом RU-1 выполнена свежая Documentation/Verification acquisition, после которой общий snapshot передан одному Documentation Qwen worker. Отдельного Main LLM-вызова и двух независимых LLM-контекстов в этом сценарии нет. Подробности: [ARCHITECTURE.ru.md](ARCHITECTURE.ru.md).

## Расположение компонентов

- `day-31-developer-assistant/` — базовое приложение, тесты, evaluation fixtures и документация. Publication Gate не установлен в его исходный `main.py`.
- [`day-31-course-minimum/`](../day-31-course-minimum/README.ru.md) — три полных проверенных пакета: v103 producer, v104-r1 anchor persistence и r3 launcher, включающий Publication Gate v104-r2. Их исходные manifests и входные evidence сохранены.
- Рабочие результаты, leases и индексы остаются вне репозитория. Исторические папки `/tmp` ещё нужны; перенос постоянного state и clean installer не реализованы.

Новые Python-файлы не помещаются внутрь базового приложения: его сохранённый source binding ожидает ровно 60 файлов. JSON в `evaluation/` — входные сценарии проверок. Зафиксированные `reports/` внутри пакетов Course Minimum нужны их manifests; новые рабочие отчёты туда не записываются.

## Установка и проверка сохранённой поставки

Команды выполняются из корня репозитория. Целевая среда — MacBook Pro M1 / 32 GB, Python 3.13+, Git. Для новой `.venv`:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r day-31-developer-assistant/requirements.lock
```

Если окружение уже установлено, достаточно активации. Проверка поставки не использует Ollama, сеть или индексы:

```bash
source .venv/bin/activate
python day-31-course-minimum/verify_delivery.py --root "$PWD"
```

Ожидается `status=passed`, `original_packages_verified=3`, `original_app_python_files_verified=60`, `mac_reports_verified=79`, `required_inputs_hidden_by_gitignore=0`, `qwen_calls=0`. Это проверка целостности и сохранённого human review, **не новая runtime/semantic приёмка**.

## Реальный MCP Git без Qwen

```bash
python day-31-developer-assistant/main.py --version
python day-31-developer-assistant/main.py --root "$PWD" git branch
python day-31-developer-assistant/main.py --root "$PWD" git status
python day-31-developer-assistant/main.py --root "$PWD" git diff --scope unstaged
```

Эти команды вызывают настоящий MCP Git server и не генерируют ответы модели. Diff без разрешённых paths не раскрывает произвольное содержимое файлов. Пустой diff после коммита допустим.

## Повторная публикация принятого ответа без Qwen

Нужен прежний внешний work directory с исходным audit, raw, evidence и изолированной копией приложения. Одних исходников из Git недостаточно для восстановления рабочего состояния. Команда использует существующее явное решение пользователя и не переносит его на новые ответы:

```bash
python day-31-course-minimum/day31-course-minimum-r3/entry.py publish \
  --root "$PWD" \
  --v103 "$PWD/day-31-course-minimum/day31-source-anchor-v103-r1" \
  --v104 "$PWD/day-31-course-minimum/day31-anchor-persistence-v104-r1" \
  --work-dir /private/tmp/day31-course-minimum-r3-work \
  --review "$PWD/day-31-course-minimum/evidence/human-review.json" \
  --reviewer-id yuriy
```

Для прежних bindings ожидается `answer_accepted=true`. Исходный withheld result, raw и evidence остаются неизменными; derived reviewed/public records сохраняются отдельно. Повтор `publish` не вызывает Qwen и создаёт следующий numbered export. При несовпадении bindings — STOP; не редактировать evidence или review ради PASS.

Без явного human review новые bindings остаются `needs_review`, `answer_accepted=false`. `unsupported` и runtime-отказы не допускаются к успешной публикации. Точное совпадение цитаты и identifiers само по себе не доказывает смысловую поддержку. Обычный `main.py ask` не является заменой принятого маршрута Publication Gate.

## Preflight и изменение корпуса

Исторический r3 preflight прошёл на Python 3.13.3: 32/32 проверки, реальные MCP/delegation и `unknown` без evidence, 0 Qwen-вызовов. Он использовал сохранённые native276 receipt, preparation bundle, production44/FTS54 и закреплённый Git HEAD. Day30 был выключен; сессия Ollama имела подтверждённый process epoch.

Команда для **того же подготовленного состояния**:

```bash
python day-31-course-minimum/day31-course-minimum-r3/entry.py preflight \
  --root "$PWD" \
  --v103 "$PWD/day-31-course-minimum/day31-source-anchor-v103-r1" \
  --v104 "$PWD/day-31-course-minimum/day31-anchor-persistence-v104-r1" \
  --work-dir /private/tmp/day31-course-minimum-r3-work
```

После нового коммита прежний Git HEAD уже не совпадает. **Обновление корневых README также меняет corpus fingerprints**, поэтому старые индексы дают stale/STOP при строгой проверке текущего корпуса. Прежний receipt не подтверждает новую ревизию; не переписывать pins, не удалять reservation и не перестраивать старый зафиксированный индекс ради PASS.

В этой документационной ревизии индексы не перестраивались. Для будущего live-поиска по изменённому корпусу потребуется отдельно подготовленный актуальный индекс и новая проверка условий. Проверка сохранённой поставки, MCP Git и публикация сохранённого принятого ответа не требуют нового Qwen-вызова. Консольный [сценарий видео](CONSOLE_VIDEO.ru.md) описывает прежнее подготовленное окружение; видео уже записано, повторная генерация не нужна.

## Сохранённые результаты

- [Итоговый Mac bundle](../day-31-course-minimum/evidence/mac-course-minimum-bundle.json): 79 отчётов с SHA; прежние 76 live reports сохранены.
- [Human review](../day-31-course-minimum/evidence/human-review.json): c1/c2 — `supported`, две claims и семь смысловых частей; решение пользователя привязано к текущим immutable bindings.
- [Принятый публичный ответ](../day-31-course-minimum/evidence/accepted-public-result.json): `answer_accepted=true`, точные source anchors и fingerprints.
- [Сводка Mac-проверки](../day-31-course-minimum/evidence/mac-publication-check.json): фактическая область приёмки.
- Один реальный Ollama chat: 1109 input / 396 output tokens, 47.67 s; без повторов и unknown inference attempts. Это один замер, не benchmark. Шесть metadata HTTP events не являются дополнительными генерациями.
- Локальная проверка размещения: 17/17 PASS, включая настоящий offline `entry.py publish` на отдельной копии сохранённого Mac-результата. Последующая Mac-проверка целостности также прошла. Это не повтор всей runtime-регрессии.

## Ограничения

Изоляция реализована на уровне application capabilities доверенного кода, **не OS sandbox**. Workspace, role, schema, deadline, call budget, path и content guards сохраняются. Синтетический model transport в тестах не выдаётся за реальную генерацию; human approval тестовых fixtures не заменяет решение пользователя.

Полный multi-task Chain, произвольные новые контексты, общий human-review workflow, EN-3 claim decomposition, финальный held-out, repeatability/resource studies и расширенная corpus44/54 calibration остаются в [backlog](BACKLOG_AFTER_COURSE.ru.md). Исторические результаты known22 не приписываются текущему producer. Прежние `CHANGES_V*`, `RESEARCH_MAC_V*` и versioned shell-runners — история разработки, не актуальная инструкция запуска.
