# Первый запуск V1

1. Распакуй `day-29-local-llm-optimization/` в корень существующего репозитория курса.
2. Открой терминал в корне репозитория. Ollama должна быть запущена.
3. Выполни:

```bash
source .venv/bin/activate
python -m pip install -r day-29-local-llm-optimization/requirements.txt
python -m unittest discover -s day-29-local-llm-optimization -p 'test_day29.py' -v
python day-29-local-llm-optimization/main.py doctor --profiles baseline
```

Если doctor готов, собери три ответа только на один вопрос:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline --case base-07 --repeats 3 \
  --output day-29-local-llm-optimization/reports/check/baseline-worker-v1.json
```

После завершения пришли `baseline-worker-v1.json`. Даже если команда вернула FAIL, сначала посмотри отчёт: ошибки и ответы сохраняются.

**Не удаляй каталог `cache/`.** При остановке повтори ту же команду: полученные валидные ответы переиспользуются, недостающие повторы выполняются. Три уже полученных ответа повторно не запрашиваются. Включение нового профиля требует его собственных ответов.

Первый запуск содержит три ответа плюс отдельно учтённые короткие проверки токенов/прогрев. Q5 пока скачивать не нужно. Полные инструкции, профили и последующие сравнения — в README.ru.md.
