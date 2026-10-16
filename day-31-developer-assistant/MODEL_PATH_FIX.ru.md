# Подготовка Ollama на Mac — v0.2.2

В минимальном служебном PATH отсутствовали `/usr/sbin` и `/sbin`. Python
`os.defpath` может содержать только `/bin:/usr/bin`. На Mac `lsof` находится
в `/usr/sbin`; протокол model session использует эту утилиту для проверки
listener Ollama, PID, владельца и времени запуска.

Добавлены явные системные каталоги, без наследования пользовательского PATH.
Проверки Day 30 и свежего процесса Ollama сохранены. Ошибка поиска утилиты
раньше могла возвращать `day30_isolation_unverified`, хотя сам сервис Day 30
был отключён. Теперь модельные команды также сохраняют безопасные диагностические
поля `probes`, если отказ возник в проверке Day 30.

Это обновление поверх v0.2.1. Распакуйте ZIP в корень репозитория с заменой
файлов. Зависимости прежние, пересборка FTS-индекса не требуется.

```bash
python day-31-developer-assistant/main.py doctor
python day-31-developer-assistant/main.py models prepare
```

После `prepared` полностью завершите и снова запустите Ollama:

```bash
osascript -e 'tell application "Ollama" to quit'
open -a Ollama
```

Когда приложение запустится:

```bash
python day-31-developer-assistant/main.py models confirm
```

После `confirmed` продолжайте сборку гибридного индекса по RAG_MAC.ru.md.
При ошибке сохраните вывод остановившейся команды, не запускайте inference.

Полная проверка новой версии:

```bash
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage3.py --output /tmp/day31-stage3-mac-v022.json
```

На Linux Python 3.13 прошли 75 тестов и реальная проверка FTS-корпуса:
40 документов / 376 фрагментов. Новые тесты проверяют обязательные системные
каталоги при коротком os.defpath и сохранение Day 30 diagnostics при отказе
модельной команды. Реальный повторный запуск model session на Mac и bge-m3
ещё требуют проверки на машине пользователя.
