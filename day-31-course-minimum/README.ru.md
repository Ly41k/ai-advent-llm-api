# Day 31 — проверенные компоненты Course Minimum

Здесь сохранены без изменения байтов три исходных пакета: `day31-source-anchor-v103-r1`, `day31-anchor-persistence-v104-r1`, `day31-course-minimum-r3`. Publication Gate v104-r2 находится внутри третьего пакета в `publication_v104r2/`. Это отдельная проверенная конфигурация, не установка gate в базовый `main.py`.

Папка соседствует с `day-31-developer-assistant`, чтобы не менять его binding из 60 Python-файлов. Все файлы исходных package manifests сохранены, включая зафиксированные входные отчёты и снимки публичного корпуса. Их нельзя путать с генерируемым `day-31-developer-assistant/reports/`, который исключён из Git. Новые run outputs сюда не писать.

Из корня репозитория, без Qwen:

```bash
python day-31-course-minimum/verify_delivery.py --root "$PWD"
```

Проверяются исходные manifests, базовые Python-файлы и requirements, документы поставки, SHA всех 79 отчётов принятого Mac bundle и привязка сохранённого human review к опубликованному результату. PASS означает целостность поставки; это не новая runtime/semantic приёмка и не новый запуск модели.

Запуск из постоянного расположения описан в [README.ru.md дня 31](../day-31-developer-assistant/README.ru.md). Это воспроизведение подготовленного состояния, не clean installer. Прежние native/preparation/work/production44/FTS54 inputs остаются внешними. Их перенос и восстановление на чистой машине не реализованы. Не удалять их, не строить новый индекс и не менять bindings для PASS.

`evidence/mac-course-minimum-bundle.json` — побайтная копия итогового Mac bundle: 79 отчётов, одна фактическая генерация RU1/Multi и положительная публикация после явного human review. Остальные три evidence-файла — прежнее review, принятый public result и компактный результат сверки. Исторические статусы внутри отчётов сохраняются; они не перезаписываются текущим состоянием.

После commit старый preflight может остановиться из-за закреплённого Git HEAD. Это не отменяет прежнюю приёмку; не объявлять её проверкой нового HEAD. Publication над сохранённым audit выполняется без Qwen и проверяет текущие immutable bindings этого результата.

Course Minimum Accepted; расширенный Research Stage 7 paused/incomplete. [Backlog](../day-31-developer-assistant/BACKLOG_AFTER_COURSE.ru.md). Commit/push/PR этот пакет не выполняет.
