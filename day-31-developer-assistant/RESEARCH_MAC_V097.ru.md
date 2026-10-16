# Mac — v097 / 0.7.27

Запускать из корня ai-advent-llm-api в активном установленном venv.
Dependencies прежние. Day30 и другие Ollama clients отключены;
выделенная сессия должна быть confirmed.

```bash
unzip -o ~/Downloads/day31-stage7-v097.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v097_mac.sh
```

Ожидаем версию 0.7.27. Архив содержит полный Day31: 59 Python файлов,
включая 10 проверочных scripts. Распаковывать через unzip из корня repo.
CURRENT 44/405 и bge-m3 не пересобирать.

Helper сначала выполняет новый preflight из 262 тестов, CURRENT verify,
retrieval admission, GET /api/version, проверки source/catalog/diagnostic plan
и fresh freeze. Preflight FTS smoke использует отдельный временный индекс
без моделей и embeddings; CURRENT он не заменяет.
Затем — только один EN Documentation control про потерю HTTP-ответа,
uncertain state и automatic cloud fallback. Generation cap1, embeddings0.
Это контроль известного дефекта; качество ещё предстоит оценить по ответу.

После завершения прикрепить один файл:

```text
/tmp/day31-stage7-mac-v097-bundle.json
```

Bundle включает 7 исходных JSON с SHA. При stopped собираются доступные файлы
и missing_files, исходный exit code остаётся ненулевым. Если bundle не создан,
прислать terminal output. Не удалять прежние reports и не повторять dispatch:
существующие файлы/bundle останавливают helper до model operations.
Нет auto retry/cloud/restart или следующего пакета. Completed validation rejection
сам по себе не означает uncertain/restart; epoch change обрабатывает session gate.
Continuation запускать после разбора этого контроля.

[Разбор v096 и изменение](CHANGES_V097.ru.md). Этап 7 открыт; начало 8 согласуем
после закрытия 7.
