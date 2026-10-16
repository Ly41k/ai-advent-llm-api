# Mac — v098 / 0.7.28

Из корня ai-advent-llm-api, в активном установленном venv. Dependencies прежние.
Day30/прочие Ollama clients выключены; выделенная сессия confirmed.

```bash
unzip -o ~/Downloads/day31-stage7-v098.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v098_mac.sh
```

Версия должна быть0.7.28. Полный Day31 содержит59Python и10 проверочных scripts.
Распаковывать через unzip из корняrepo. CURRENT44/405 и bge-m3 не пересобирать.

Helper: новый262-test preflight, CURRENTverify/admission/GETversion, source/catalog/
plan guards, fresh freeze. PreflightFTSsmoke temporary, generation0/embeddings0.
Затем один RU Documentation вопрос о потере HTTP-ответа, uncertain state и
automatic cloud fallback: cap1, embeddings0. Цель — проверить повторы и язык
на известном входе. Качество модели ещё не подтверждено. Автоматического
следующего пакета нет; continuation только после review.

Прикрепить один файл:

```text
/tmp/day31-stage7-mac-v098-bundle.json
```

Bundle содержит7 исходных JSON с SHA; при ошибке — доступные reports и missing_files
с исходным exit code. Если bundle не появился — прислать terminal output.
Старые reports сохранять. При остановке не повторять dispatch самостоятельно:
существующие выходные файлы/bundle останавливают helper до model operations.
Нет automatic retry/cloud/restart. Completed validation rejection сам по себе
не означает uncertain/restart; изменение epoch обрабатывает session gate.

[Изменения и ограничения](CHANGES_V098.ru.md). Этап7 открыт; начало8 согласуем
после закрытия7.
