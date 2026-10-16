# Инструменты и модельная сессия

## Read-only инструменты Git дня 31

День 31 предоставляет git_current_branch, git_status, git_diff и
project_list_files через локальный FastMCP stdio server. Входы и выходы
проверяются. Только scoped client роли Git может вызывать эти инструменты.
Пути относительны корню репозитория; traversal и symlinks отклоняются.

git_diff по умолчанию возвращает metadata. Содержимое требует от одного до
четырёх явных allowed paths. Содержимое untracked файлов не читается, даже если
путь явно разрешён. Sensitive names и private databases исключены;
patches с признаками secret блокируются.

Контролируемый runner отключает hooks, external diff, textconv, fsmonitor и
настроенные clean/smudge/process filters. Произвольный Bash не выполняется.
Application capabilities не являются OS sandbox для враждебного Python-кода.

## Явные записи и подтверждение

Git tools не выполняют commit, push, изменение или удаление файлов проекта.
Явный index build записывает производное app state вне проекта с приватными
permissions. Будущие write tools должны связывать human approval с конкретными
проверенными аргументами действия и project revision. Опасный executor не
добавляется только ради демонстрации approval.

## Остановка других модельных клиентов

Перед embedding/inference дня 31 сервис дня 30 должен быть остановлен.
Doctor проверяет известные процессы, launchd и loopback ports. Неактивность
сервиса сама по себе не доказывает завершение прежнего запроса Ollama.

## Ollama /api/ps: загруженные модели и состояние запросов

GET /api/ps показывает модели, загруженные в память (model residency).
Это не запись о завершении inference. Загруженная модель не доказывает,
что генерация закончилась или Ollama свободна. После потерянного HTTP-ответа
или прерванного запроса /api/ps нельзя использовать как idle witness.

API contract: https://docs.ollama.com/api/ps . Ограничение idle witness — policy
дня 31, реализованная в model_session.py.

## Новые process epochs и выделенная модельная сессия

День 31 использует prepare/confirm. Оператор перезапускает Ollama; приложение
подтверждает новый OS process epoch и отсутствие отдельного старого runner.
Межпроцессный cooperative lease разрешает одну model operation. Перед dispatch
сохраняется uncertain state; потеря ответа или crash требуют проверяемого recovery.
Другие приложения не должны использовать эту выделенную сессию.

Используется одна модель Qwen, а не отдельная копия для каждого агента.
Git и retrieval могут выполняться параллельно; модельные вызовы последовательны
через общую lease. Финальный embedding batch/query выгружает bge-m3 с keep_alive=0s.
Автоматического cloud fallback нет.

## Цепочка ответов и связь изменённых путей с документацией

/help question и ask выбирают Git, документацию, независимый fan-out или
цепочку changed-files documentation. Цепочка проверяет максимум четыре
изменённых пути на связь с документацией. Association использует точное
упоминание относительного пути, а не basename. Найденная связь не подтверждает
всю функциональность файла: документ может описывать только часть.
Отсутствие association сообщается явно.

## Генерация и финальная проверка ответа дня 31

Qwen2.5:14b Q4_K_M формирует claims по scoped excerpts через /api/chat с закрытой
JSON schema. Documentation не видит Git-факты caller и private history.
Main имеет отдельный контекст и выбирает только проверенные claim/fact IDs.
На запрос разрешены восемь capability calls и deadline 300 секунд;
каждый model worker имеет timeout 180 секунд.

При потере HTTP-ответа сохраняется uncertain inference state. Автоматические
повтор, cloud fallback и model restart не разрешены; требуется проверяемое recovery.
Финальный verifier проверяет свежие source digests/spans и повторно наблюдает Git
после генерации. Точные цитаты и identifier checks отделены от semantic correctness.
Записи и произвольные shell-команды остаются недоступны.

Источники: day-31-developer-assistant/bublik_developer/policy.py;
day-31-developer-assistant/bublik_developer/preflight.py;
day-31-developer-assistant/bublik_developer/model_session.py;
day-31-developer-assistant/bublik_developer/pipeline.py.
