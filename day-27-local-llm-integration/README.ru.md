[English](README.md) | **Русский** | [К проекту](../README.ru.md)

# День 27. Интеграция локальной LLM в приложение — Ревик

**Ревик (Revik)** — CLI-агент проверки Kotlin-кода перед коммитом. Он запускает настоящий Detekt по конфигурации проекта, отправляет результаты в локальную Qwen через Ollama, показывает объяснения и ссылки на файлы, затем разрешает или блокирует Git-коммит.

Это отдельное приложение для практического использования в Kotlin Multiplatform-проекте. Оно не использует RAG-индекс Бублика, MCP или облачные модели. Detekt выполняет правила статического анализа; LLM помогает понять нарушения и предлагает исправления. Свободный текст модели не меняет решение о найденных нарушениях.

## Результат задания

| Требование | Реализация |
|---|---|
| Интегрировать модель в приложение | Python CLI + Git pre-commit hook |
| Отправлять запросы в локальную LLM | Ollama `/api/show` и `/api/chat`, скачанная Qwen |
| Получать и отображать ответы | Терминал и JSON/Markdown/HTML-отчёты |
| Работать без облачных моделей | Только loopback Ollama; API-ключи и cloud fallback отсутствуют |

В текущем коде исправлен отчёт при `llm=null`, добавлены русский/английский язык и три стиля комментариев. **28 интеграционных тестов проходят**. Настоящий Detekt CLI 1.23.8 также проверен на good/bad примерах. Тесты Ollama используют scripted HTTP-сервер; они не заменяют живую проверку Qwen. Подробнее: [VALIDATION.md](VALIDATION.md).

## Как работает проверка

```text
Git commit → pre-commit → snapshot Git index → Detekt → локальная LLM
           → объяснение + ссылки + отчёт → exit code → коммит или отказ
```

Ревик сравнивает дерево Git index с HEAD, выбирает добавленные/изменённые `.kt` и `.kts` и извлекает их staged-содержимое во временный каталог. Частично добавленные файлы проверяются в той версии, которая должна попасть в коммит. Удалённые Kotlin-файлы не анализируются, переименованные проверяются под новым именем.

На первом коммите, а также при изменении Detekt-конфигурации или настроенного baseline, проверяется всё staged Kotlin-дерево. Перед завершением повторно проверяется tree ID: изменение index во время анализа блокирует коммит. Рабочие исходники не исправляются, index/stash не подменяются.

| Ситуация | Результат |
|---|---|
| Конфигурации `detekt/detekt.yml` нет в index | `skipped`, коммит разрешён, LLM не вызывается |
| Нет выбранных Kotlin-файлов | `skipped`, коммит разрешён, LLM не вызывается |
| Detekt обнаружил нарушения | `blocked`, коммит отклонён |
| Ошибка Detekt / отсутствует корректный свежий XML | `error`, коммит отклонён |
| Detekt чистый, модель ответила штатно | `allowed`, коммит разрешён |
| Модель недоступна или ответ неполный, `require_llm=true` | `error`, коммит отклонён |
| Та же ошибка, `require_llm=false` | Решение остаётся по Detekt; ошибка LLM сохраняется |

Ревик блокирует коммит при любых findings в XML, даже если порог Detekt позволил самому Detekt вернуть 0. Baseline, suppressions и исключения применяет Detekt. Коды CLI: **0** — allow/skip, **1** — нарушения, **2** — техническая ошибка, **130** — прерывание.

## Проверка в репозитории курса

Все команды в этом разделе выполняются **из корня `ai-advent-llm-api`**.

Требования: macOS/Linux, Git, Python 3.10+ (целевая версия курса — 3.13), совместимый JDK, Detekt CLI, запущенный Ollama и скачанная локальная модель. Python-модуль использует стандартную библиотеку; дополнительных pip-зависимостей нет.

```bash
source .venv/bin/activate
python -m unittest discover -s day-27-local-llm-integration/tests -v
```

Для живой демонстрации скачай Detekt и модель заранее. Версия 1.23.8 проверена для примеров этого дня; в рабочем проекте используй версию, совместимую с его Gradle-конфигурацией и плагинами.

```bash
java -version
mkdir -p day-27-local-llm-integration/.vendor
curl --fail --location \
  https://github.com/detekt/detekt/releases/download/v1.23.8/detekt-cli-1.23.8-all.jar \
  --output day-27-local-llm-integration/.vendor/detekt-cli.jar

# Если Ollama и модель уже установлены, повторная установка не нужна.
open -a Ollama
ollama pull qwen2.5:14b

python day-27-local-llm-integration/live_demo.py \
  --detekt-jar day-27-local-llm-integration/.vendor/detekt-cli.jar \
  --model qwen2.5:14b --language ru --tone light_troll \
  --output day-27-local-llm-integration/revik-live.json
```

На Linux вместо `open -a Ollama` запусти локальный сервер Ollama. Если API уже работает, второй сервер не нужен. Можно использовать установленный Detekt CLI: замени `--detekt-jar ...` на `--detekt-bin /absolute/path/to/detekt`.

`live_demo.py` создаёт временный Git-репозиторий, копирует конфигурацию из `examples/`, устанавливает настоящий hook и пробует два коммита:

1. `Bad.kt`: локальный `val factor = 42` → `MagicNumber` → объяснение LLM → отказ коммиту.
2. `Good.kt`: `private const val FACTOR = 42` → чистый анализ → ответ LLM → успешный коммит.

Проверяемые файлы в обоих случаях называются `Demo.kt`. Рабочий KMP-проект не изменяется. При успешном завершении JSON содержит `all_passed=true`, ответы модели и ожидаемые коды Git. Это проверка запуска и поведения приложения, а не автоматическая оценка правильности рекомендаций. При технической ошибке демонстрация может завершиться раньше сохранения итогового JSON; смотри вывод консоли.

Для видео покажи `ollama list`, команду demo, ответ модели, заблокированный плохой коммит и успешный исправленный. После скачивания модели и Detekt повтори без интернета. Не устанавливай hook в учебный репозиторий ради demo: скрипт ставит его сам во временный репозиторий.

## Подключение к рабочему KMP-проекту

Скопируй содержимое этой папки в `tools/revik-agent/` **в корне целевого проекта**:

```bash
# Выполняется из корня ai-advent-llm-api. Укажи свой путь.
mkdir -p /absolute/path/to/EventConnectMobile/tools/revik-agent
cp -R day-27-local-llm-integration/. /absolute/path/to/EventConnectMobile/tools/revik-agent/
cd /absolute/path/to/EventConnectMobile
```

Структура целевого проекта:

```text
EventConnectMobile/
  detekt/detekt.yml
  common/
  composeApp/
  tools/revik-agent/
  .revik.json
```

Создай **локальный** `.revik.json` в корне KMP-проекта. Для CLI из PATH можно скопировать шаблон:

```bash
cp tools/revik-agent/revik.example.json .revik.json
```

Для отдельного JAR используй настройки ниже; сохрани свои пути и версию Detekt:

```json
{
  "language": "ru",
  "tone": "light_troll",
  "detekt_config": "detekt/detekt.yml",
  "detekt_command": ["java", "-jar", "tools/revik-agent/.vendor/detekt-cli.jar"],
  "detekt_plugins": [],
  "baseline": null,
  "build_upon_default_config": false,
  "model": "qwen2.5:14b",
  "ollama_url": "http://127.0.0.1:11434",
  "require_llm": true
}
```

`build_upon_default_config` согласуй с `buildUponDefaultConfig` в Gradle. Если модель 14B уже установлена, её повторно скачивать не нужно; для 7B измени `model`. Для коммитов из IDE при отличающемся PATH можно задать абсолютный путь к `java`/`detekt`.

```bash
python3 tools/revik-agent/revik_cli.py doctor
python3 tools/revik-agent/revik_cli.py install

# Конфигурация и проверяемые изменения должны быть staged.
git add detekt/detekt.yml
# Добавь нужные Kotlin-файлы через git add или git add -p.
python3 tools/revik-agent/revik_cli.py check
git commit -m "Update transfer state handling"
```

`doctor` показывает настройки, проверяет Detekt `--version` и делает реальный запрос в локальную модель. `check` проверяет текущий index. `install` записывает pre-commit с абсолютными путями к Python и CLI; после переноса проекта/замены venv повтори установку. Можно также запускать `python -m revik check` из каталога, где доступен пакет `revik`.

В рабочем проекте добавь в корневой `.gitignore`:

```gitignore
/tools/revik-agent/
/.revik.json
/revik-live.json
```

Если эти файлы уже tracked, `.gitignore` не удалит их из index. Убрать только отслеживание, сохранив файлы на диске:

```bash
git rm -r --cached --ignore-unmatch tools/revik-agent
git rm --cached --ignore-unmatch .revik.json revik-live.json
```

В **репозитории курса**, напротив, исходники дня, документация, `revik.example.json` и `examples/` коммитятся. Локальные `.vendor/`, `.revik.json`, venv, Python cache и `revik-live.json` не коммитятся. Примеры нужны для demo, но не для обычного hook.

## Язык и комментарии

| Параметр | Значения | По умолчанию |
|---|---|---|
| `language` | `ru`, `en` | `ru` |
| `tone` | `professional`, `light_troll`, `hard_troll` | `professional` |

`professional` — деловое объяснение и исправление. `light_troll` — максимум одна дружеская шутка про код. `hard_troll` — максимум две более острые шутки про реализацию; исправления остаются основным содержанием. Пример лёгкого стиля: «Походу, этот баг у нас уже член команды» — метафора, а не сохранённая история багов. Шутки направлены на код, а не на разработчика.

Интерфейс и заголовки отчётов переводит приложение; язык и стиль ответа задаются модельной инструкцией. Оригинальные сообщения Detekt и технические диагностики не переводятся. Соблюдение стиля локальной моделью требует живого просмотра и не гарантируется тестами.

```bash
python3 tools/revik-agent/revik_cli.py check --language en --tone professional
python3 tools/revik-agent/revik_cli.py doctor --language ru --tone hard_troll
```

Флаги действуют на один вызов. Для автоматических коммитов меняй `.revik.json`: hook читает его при каждом запуске, переустановка не нужна.

## Отчёты и настройки

Отчёты находятся по пути `git rev-parse --git-path revik-reports`: `latest.json`, `latest.md`, `latest.html`. В обычном репозитории это `.git/revik-reports/`. Каждый запуск заменяет предыдущий отчёт, включая skip/error. JSON и Markdown записываются через временный файл; HTML — обычной записью. Файлы отчётов не входят в commit.

В консоли нарушения печатаются как `/absolute/path/File.kt:line:column`. Markdown/JSON содержат `file://` и `vscode://` ссылки, HTML — ссылки VS Code. Поддержка клика зависит от терминала/IDE и установленного обработчика протокола.

**Номера строк относятся к staged-версии, ссылки открывают рабочий файл.** При unstaged-правках строки могут отличаться. JSON сохраняет tree ID, language/tone и, при ответе LLM, модель, ответ, SHA-256 сообщений, время HTTP chat-запроса и token counts.

| Дополнительный параметр | По умолчанию |
|---|---|
| `detekt_timeout`, `llm_timeout` | 180 секунд каждый |
| `num_ctx` | 8192 |
| `num_predict` | 1500 |
| `max_findings_for_llm` | 12 |
| `snippet_lines` | 3 с каждой стороны, до 300 символов на строку |

Все findings сохраняются, но в LLM отправляется ограниченная выборка с кратким staged-контекстом. Для чистого анализа модель получает только сводку. `.revik.json` читается из рабочего каталога репозитория; Detekt YAML и baseline — из index. Неизвестные ключи настройки отклоняются.

`baseline` — один явно указанный repository-relative XML, уже staged. Каталог `detekt/baselines/` автоматически не обходится. `detekt_plugins` — список установленных локальных совместимых rules JAR. При `baseline=null` старые нарушения изменённого файла также могут блокировать commit.

## Исключения и границы анализа

Для MVI reducer можно подавить только длину и сложность конкретной функции:

```kotlin
@Suppress("LongMethod", "CyclomaticComplexMethod")
override fun reduce(/* existing parameters */): State {
    // existing state handling
}
```

Это шаблон: сохрани свои параметры и тип состояния. Остальные правила и методы продолжают проверяться. Исключение всего `*ViewModel.kt` через YAML `excludes` имеет более широкую область действия. После правки добавь файл в index.

Ревик использует Detekt CLI **без type resolution**: это анализ AST, а не замена компиляции KMP, Android Lint или платформенных Gradle-задач. Правила, которым нужны resolved types, могут не выполниться. Версия CLI должна соответствовать конфигурации и плагинам проекта; проверена 1.23.8, совместимость с 2.x не заявлена.

Проверяется весь изменённый файл, а не только изменённые строки. Несколько baseline по модулям/вариантам не поддерживаются. Внешние ресурсы, на которые ссылается YAML (например шаблон лицензии), автоматически не копируются. Symlink-исходники/конфигурации отклоняются; содержимое Git submodule не обходится.

Локальный URL ограничен loopback HTTP, прокси и redirects отключены. Cloud-теги и `remote_host`/`remote_model` отклоняются. Это предполагает обычную локальную установку Ollama, а не аттестацию любого сервера на loopback.

## Hook: объединение и отключение

Установщик учитывает `core.hooksPath` и worktree через `git rev-parse --git-path hooks/pre-commit`. Чужой pre-commit не перезаписывается. В существующий общий hook добавь один вызов перед его успешным завершением:

```sh
python3 tools/revik-agent/revik_cli.py check || exit $?
```

Пропустить pre-commit и commit-msg на один коммит:

```bash
git commit --no-verify -m "Commit without pre-commit checks"
```

Временно отключить **отдельный hook, установленный Ревиком**:

```bash
revik_hook_path="$(git rev-parse --git-path hooks/pre-commit)"
mv "$revik_hook_path" "$revik_hook_path.disabled"
```

Включить обратно:

```bash
revik_hook_path="$(git rev-parse --git-path hooks/pre-commit)"
mv "$revik_hook_path.disabled" "$revik_hook_path"
```

В общем hook закомментируй только вызов Ревика. Git hooks локальные, устанавливаются отдельно каждым разработчиком и могут быть обойдены; обязательный контроль проекта сохраняй в CI.

## Файлы

| Файл | Назначение |
|---|---|
| `revik_cli.py`, `revik/__main__.py` | Точки входа |
| `revik/app.py` | Git snapshot, Detekt, Ollama, отчёты, установка hook |
| `revik/i18n.py` | Переводы интерфейса и инструкции стилей |
| `revik.example.json` | Публичный шаблон локальных настроек |
| `live_demo.py`, `examples/` | Живая проверка двух Git-коммитов |
| `tests/test_revik.py` | 28 offline интеграционных тестов |
| `VALIDATION.md` | Зафиксированные проверки реализации |

Документация API: [Detekt CLI](https://detekt.dev/docs/1.23.8/gettingstarted/cli/), [type resolution](https://detekt.dev/docs/1.23.8/gettingstarted/type-resolution/), [suppressions](https://detekt.dev/docs/1.23.8/introduction/suppressing-rules/), [Git hooks](https://git-scm.com/docs/githooks), [Ollama chat](https://docs.ollama.com/api/chat).
