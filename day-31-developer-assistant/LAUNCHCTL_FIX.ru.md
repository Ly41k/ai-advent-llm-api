# 0.1.2 — print-disabled на macOS

Подтверждённый вывод Mac: `"local.bublik.private-ai.api" => disabled`.
Отсутствие процессов и listener на 8000 подтверждено doctor 0.1.1;
старый guard ошибочно отклонил текстовый формат disabled/enabled.

0.1.2 поддерживает оба формата: true/false и disabled/enabled. Разрешается
только ровно одна точная строка нужного label со значением true или disabled.
Enabled/false, неизвестный формат, чужой label и duplicate не проходят.
Прочие проверки отключения сервиса и ограничения остаются прежними.

Linux/Python 3.13.16: 40/40 tests; отдельный immutable report.
Mac-проверка новой версии выполняется оператором после замены файлов.

Распаковать архив в корень repo с заменой совпадающих файлов, затем:

```bash
python day-31-developer-assistant/main.py doctor
```

Ожидаются version=0.1.2, status=passed, launchd.disabled=true, day30_off=true.
ollama_idle_verified=false остаётся корректным: model stage ещё не реализован.
