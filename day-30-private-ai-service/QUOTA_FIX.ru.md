# Исправление live checker этапа 4

Распакуйте day30-stage4-quota-fix.zip в корень репозитория: архив содержит
префикс day-30-private-ai-service/. Он обновляет только checker, tests/docs
и добавляет отчёты. Runtime API, модель, база, зависимости и лимиты не менялись.
Перезапуск serve не требуется. Старые отчёты сохраняются без изменения.

Mac offline report: 106/106 passed, manifest проверен до изменения checker.
Новый полный Linux suite: 109/109 passed, включая три регрессионных проверки.
Mock HTTP/virtual clock не являются доказательством real Qwen или LAN.

Проблема: Retry-After гарантирует открытие первого слота скользящей квоты.
Три конкурентных запроса после такого ожидания могут получить [202,429,429].
Checker теперь ждёт max(61, Retry-After+1) секунд после контрольного 429.
Добавлены concurrent_admissions (HTTP status/безопасный error code) и failed_check.
Скрипт не переписывает старые reports и не повторяет принятую генерацию.

Из day-30-private-ai-service/ в вашем активном venv, используя тот же запущенный API:

```bash
BUBLIK_STAGE4_DIR="/Users/litdi/bublik-day30-stage4.V1EM3F"
python scripts/check_http_live.py \
  --token-file "$BUBLIK_STAGE4_DIR/check-token.json" \
  --output "$BUBLIK_STAGE4_DIR/http-live-v2.json"
```

Во время теста другие приложения не должны отправлять генерации от этого же
пользователя. Если предыдущий run закончился менее минуты назад, дайте старой
квоте истечь перед повторным запуском. Для следующего повторения выберите ещё
одно новое имя отчёта. Успех ожидается только при status=passed.

Сохраните и пришлите исходный failed http-live.json и новый http-live-v2.json.
Приложенный ранее 20261009T190907-71a14e3f.json — offline report, не failed live
report, поэтому точная причина предыдущего реального run пока не подтверждена.
Не отправляйте check-token.json, пароль, cookie или SQLite database.

После passed продолжайте проверку рестарта из STAGE4.ru.md, передав
--history-from "$BUBLIK_STAGE4_DIR/http-live-v2.json" и новое имя output.
