# Бублик — русский и английский, 0.10.0

> Для установленной 0.10.2 примените [исправление 0.10.3](LANGUAGE_EXPLICIT_HINT_FIX.ru.md).
> Для установленной 0.10.1 примените [исправление 0.10.2](LANGUAGE_HINT_FIX.ru.md).
> Для установленной 0.10.0 примените [исправление 0.10.1](LANGUAGE_FIX.ru.md).
> Оно сохраняет schema 3 и убирает конфликт инструкций языка ответа.

Поддерживаются два кода: `ru` и `en`. Язык интерфейса и язык новых ответов
выбираются независимо в боковой панели. Например, русский интерфейс может
получать английские ответы. Настройки принадлежат пользователю и хранятся
на сервере: Mac, Android и iPhone загружают их после входа тем же username.

До входа язык выбирается на экране авторизации; начальный выбор берётся из
поддерживаемых языков браузера, иначе русский. После входа действуют настройки
владельца. Существующим и новым владельцам миграция задаёт `ru` / `ru`.
Настройки перечитываются при открытии приложения, кнопкой обновления диалога
и периодически, до 60 секунд в активной вкладке. Фоновую вкладку обновляет браузер
после возвращения; это не отдельный канал мгновенной синхронизации настроек.

## Что меняется и что сохраняется

- Переведены экран входа, кнопки, настройки, статусы доставки/модели, ошибки,
  сведения об источниках памяти и подписи исходного разговора. Даты используют
  locale выбранного интерфейса. Manifest PWA имеет RU/EN варианты.
- Web UI явно отправляет `reply_language`. Языковая инструкция входит в бюджет
  контекста и сохраняется в snapshot генерации; поздняя смена настройки не меняет
  начатый ответ или повтор с тем же idempotency key.
- Исторический profile `private-chat-v2` и параметры Qwen остаются прежними;
  0.10.3 сохраняет эффективную первую инструкцию по выбранному языку и добавляет
  явную подсказку с приоритетом языка настройки над пожеланиями в вопросе к последнему
  вопросу только в inference snapshot. Исходный вопрос в истории не изменяется:
  temperature 0, output 1024, num_ctx 8192, margin 512. Добавленная инструкция
  уменьшает место для недавних сообщений; полная история остаётся в SQLite.
- Исходные сообщения, названия диалогов, цитаты памяти и прежние snapshots
  не переводятся и не переписываются. Новый язык действует на следующие ответы.
- API v1 без `reply_language` сохраняет прежний выбор языка по сообщению и
  прежние fingerprints повторов. Настройка аккаунта сама по себе не меняет
  старых внешних клиентов: новый клиент должен передать выбранный код явно.
- Секреты, настройки и история не записываются в localStorage/sessionStorage.
  Доступ к настройкам использует ту же авторизацию и browser CSRF/Origin защиту.

Инструкция направляет модель, но не гарантирует язык каждого произвольного
ответа. Имена, код, буквальные цитаты и явно запрошенные переводы могут содержать
другой язык. Нет автоматической перегенерации или облачного fallback.
Проверка реальной Qwen выполняется отдельно от synthetic tests.

## Обновление действующей установки на Mac

База обновления: `main` **63adc4ca542f17f29495f6ac8412ddc96ad7e320**, runtime
0.9.1. Патч меняет только день 30 и корневые README. Сначала проверяется
применимость; затем сохраняется backup **старой версией**, до миграции.
Не запускайте второй API и не меняйте существующие LaunchAgents/Serve/origins.

### 1. Проверить патч, пока сервис работает

Скачайте `bublik-languages-v1.zip` в Downloads. Из корня репозитория:

```bash
cd /Users/litdi/AI/ai-advent-llm-api
source .venv/bin/activate
git status --short
BUBLIK_LANG_PATCH_DIR="$(mktemp -d "$HOME/bublik-languages-update.XXXXXX")"
unzip "$HOME/Downloads/bublik-languages-v1.zip" -d "$BUBLIK_LANG_PATCH_DIR"
git apply --check "$BUBLIK_LANG_PATCH_DIR/bublik-languages-v1.patch"
```

При конфликте не используйте force/`--reject`: сначала разберите отличия.
Проверка патча не применяет изменения. Сохраните эту терминальную вкладку:
переменные используются дальше.

### 2. Дождаться сохранённых ответов, остановить API, сделать backup

Закончите отправку со всех устройств. Дождитесь «Ответ сохранён» и idle:
queued=running=0, inference_recovery_required=false; readiness проверяется по
[RUNBOOK.ru.md](RUNBOOK.ru.md). Остановите API и дождитесь отсутствия listener:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
cd day-30-private-ai-service
BUBLIK_DB="/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3"
BUBLIK_PRE_LANG_ARCHIVE="$HOME/bublik-memory-archives/pre-languages-$(date +%Y%m%d-%H%M%S)"
python scripts/memory_archive.py create --db "$BUBLIK_DB" --output "$BUBLIK_PRE_LANG_ARCHIVE"
python scripts/memory_archive.py verify --archive "$BUBLIK_PRE_LANG_ARCHIVE"
```

Listener должен отсутствовать; create и verify должны завершиться успешно.
Не создавайте каталог архива заранее и не используйте прежний путь.
Архив содержит личную историю и хеши паролей; он приватный, но не зашифрован.
Ollama, Tailscale и Caddy могут оставаться запущенными.

### 3. Применить код, мигрировать базу и проверить

```bash
cd ..
git apply "$BUBLIK_LANG_PATCH_DIR/bublik-languages-v1.patch"
cd day-30-private-ai-service
python -c 'from bublik_service import __version__; print(__version__)'
python -m bublik_service --db "$BUBLIK_DB" init-db
python -m bublik_service --db "$BUBLIK_DB" storage-status
python scripts/verify_report.py reports/verified/languages-offline-20261011.json
BUBLIK_LANG_CHECK="$(mktemp -d "$HOME/bublik-languages-check.XXXXXX")"
python -W error::ResourceWarning scripts/check_storage.py --output "$BUBLIK_LANG_CHECK/offline.json"
python scripts/verify_report.py "$BUBLIK_LANG_CHECK/offline.json"
```

Ожидаются версия **0.10.0**, schema **3**, integrity `ok`, foreign key violations 0,
queued/running 0 и recovery false. Migration `003_languages.sql` добавляет только
таблицу настроек и trigger для новых пользователей. `001` / `002` не изменены.
История, owners, IDs, receipts и старые context/profile JSON сохраняются.
Offline suite работает с временными базами и synthetic inference, без личной базы.
Сравнение отчёта с хешами — не подпись и не доказательство реальной сети/модели.

**Старый runtime 0.9.1 не открывает schema 3.** После миграции нельзя просто
откатить код и подключить его к этой базе. При необходимости rollback выполняется
через проверенный прежний архив в **новый** файл и отдельное переключение пути
сервиса. Не перезаписывайте рабочую базу и не теряйте новые сообщения после backup.

### 4. Запустить и проверить устройства

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Проверьте readiness и совпадение runtime hashes по RUNBOOK. Повторно откройте
чат или обновите страницы на Mac/телефонах, чтобы загрузить новый JavaScript.
Используйте тот же username и прежний Tailscale URL.

1. На Mac выберите **English** для интерфейса и **Русский** для ответов.
   Создайте диалог, задайте вопрос на английском: ответ ожидается по-русски.
2. На телефоне откройте тот же диалог: исходный вопрос/ответ должны совпасть.
   Проверьте независимые значения обоих select; обновите диалог при необходимости.
3. Выберите **English** для ответов. Задайте русский вопрос: ожидается английский
   ответ и **Reply saved**. Старый русский ответ должен остаться исходным.
4. Переключите интерфейс на русский: кнопки/статусы и подписи источников меняются,
   сохранённые тексты не меняются. Откройте прежний RAG-источник.
5. Повторите на Android и iPhone; после restart API и повторного входа выбранные
   настройки и вся история должны остаться. На mobile data используйте Tailscale.

Сохранённый значок PWA может оставить прежнее имя: обновление manifest не обещает
автоматическое переименование значка средствами Android/iOS.

## Реальный HTTP/Qwen отчёт

В активном сервисе запускайте отдельно, без других генераций:

```bash
python scripts/check_languages_live.py \
  --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_LANG_CHECK/live.json"
python scripts/verify_report.py "$BUBLIK_LANG_CHECK/live.json"
```

Токену нужны chats:read, chats:write и service:read. Checker создаёт два отдельных
контрольных диалога, сохраняет IDs, хеши ответов и метрики без текста. Проверяет
завершение, snapshot выбранного языка, неизменность входного сообщения и простой
языковой контроль при вопросе на противоположном языке. Это ограниченный тест,
не семантическая оценка произвольных ответов. Настройки аккаунта он не меняет.
Если токен истёк, создайте новый CLI-токен; не вставляйте его в JavaScript.
Повторный запуск использует новый путь отчёта; предыдущий JSON сохраняется.

## Автоматическая проверка и ограничения

Отчёт `reports/verified/languages-offline-20261011.json`: **216/216**, без ошибок
и пропусков, 80 source files, Linux/Python 3.13.16/SQLite 3.53.1. Полный regression
suite проверяет сохранность настроек, конкурентное обновление, owner isolation,
CSRF/scopes, язык snapshot, idempotency, контекстный бюджет, каталоги переводов,
миграции и архивы schema 2/3. Это SQLite/HTTP tests с synthetic engine, не Qwen.

Дополнительный браузерный checker требует optional dependencies и установленный
Chromium; он также использует synthetic inference:

```bash
python -m pip install -r requirements.browser.lock
python -m playwright install chromium
python scripts/check_languages_ui.py --output "$BUBLIK_LANG_CHECK/browser.json"
python scripts/verify_report.py "$BUBLIK_LANG_CHECK/browser.json"
```

В среде подготовки Chromium и реальная Ollama отсутствуют; новый браузерный,
Qwen и физический RU/EN device acceptance не объявляются пройденными.
Прежние RU/EN RAG live-проверки не заменяют приёмку этой версии.
FTS5 остаётся лексическим: английский вопрос не гарантирует нахождение русской
памяти и наоборот. Semantic multilingual retrieval — отдельный следующий этап.

Архив v1 теперь читает точные схемы 2 и 3: старый архив восстанавливается без
изменения его истории/схемы, затем новая версия мигрирует восстановленную копию.
Новые архивы schema 3 включают языковые настройки; credentials сбрасываются
только в восстановленной копии. Перенос на физически другой компьютер остаётся
отдельной проверкой. Политика сохранения оригиналов не меняется.

Root README обновлены; перед будущим strict repository RAG пересоберите корпус
дня 21 отдельно от приёмки Qwen. День 30 этот индекс не использует.
