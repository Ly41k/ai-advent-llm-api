# Язык ответа: подсказка в текущем вопросе — 0.10.2

Патч для установленной **0.10.1** с двумя выданными диагностическими scripts.
Схема SQLite остаётся **3**, SQL migrations и настройки моделей не меняются.
Не применяйте этот патч напрямую к 0.9.1 или 0.10.0.

## Что установлено реально

В Ollama 0.40.3 / Qwen2.5:14b Q4_K_M оператор проверил контрольные вопросы без
приложения. Короткий кандидат с дополнительными правилами: English 0/3,
Russian 3/3, факт 37 из RAG 2/2. Отдельные добавления имени Bublik и правил об
источниках сопровождались русским ответом на русский вопрос при English only.
Минимальная English system-инструкция также не удержала язык с русской историей
или архивом. Это наблюдения для конкретных вопросов, не общая причинная модель.

Добавление `Answer in English only.` к текущему вопросу при полном коротком
кандидате дало английский ответ в одном проверенном запросе. Новый runtime
с прежним v2 root, таким hint, multi-turn и RAG ещё требует live проверки ниже.
Сохранены исходные диагностические отчёты в `reports/experiments/`; их ошибки
не заменены успешными результатами и они не являются acceptance отчётами.

## Поведение нового runtime

Для явного `reply_language` новый snapshot имеет `reply-language-v3`:

- Первая system-инструкция остаётся эффективным v2 root с выбранным языком.
- Последний user message для модели получает `\n\nAnswer in English only.`
  либо `\n\nAnswer in Russian only.`. Это правило сервиса, не исправление
  сохранённого текста пользователя. История, RAG quotes и предыдущие пары
  передаются с исходным содержимым, без добавления hints к старым сообщениям.
- В приватном snapshot сохраняются исходный вопрос и точный отправляемый
  контекст. Подсказка учитывается при admission, выборе истории и проверке
  бюджета 8192 / output 1024 / margin 512. В API отдаётся только metadata
  `language_hint` с версией и хешами original/rendered; полные prompts скрыты.
- Перед отправкой adapter проверяет точный suffix и hashes. Нет скрытого
  переписывания в adapter, автоматического перевода или replay генераций.
- Старые snapshots без language, v1 и v2 отправляются без изменения. Старые
  receipts с тем же idempotency key возвращаются как раньше. История не
  переводится, schema/owners/IDs не меняются, архивы schema 2/3 совместимы.

Инструкция не гарантирует язык произвольного ответа. При провале live проверки
сохраняйте отчёт; не объявляйте поддержку English проверенной.

## Установка

Скачайте `bublik-languages-fix-v3.zip` в Downloads. Два ранее скачанных
diagnostic scripts должны быть в `day-30-private-ai-service/scripts/`;
они включены в ZIP отдельно, чтобы можно было восстановить точные исходники.
Если этих файлов нет, скопируйте их из ZIP. Патч не перезаписывает их.

```bash
cd /Users/litdi/AI/ai-advent-llm-api
source .venv/bin/activate
BUBLIK_LANG_V3_DIR="$(mktemp -d "$HOME/bublik-language-v3.XXXXXX")"
unzip "$HOME/Downloads/bublik-languages-fix-v3.zip" -d "$BUBLIK_LANG_V3_DIR"
git apply --check "$BUBLIK_LANG_V3_DIR/bublik-languages-fix-v3.patch"
```

При конфликте применения не используйте force/reset. При уже остановленном API
не повторяйте bootout. Иначе дождитесь сохранения ответов и пустой очереди:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
```

Listener должен отсутствовать. Для дополнительной копии перед обновлением:

```bash
cd day-30-private-ai-service
BUBLIK_PRE_HINT_ARCHIVE="$HOME/bublik-memory-archives/pre-language-hint-$(date +%Y%m%d-%H%M%S)"
python scripts/memory_archive.py create \
  --db "/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3" \
  --output "$BUBLIK_PRE_HINT_ARCHIVE"
python scripts/memory_archive.py verify --archive "$BUBLIK_PRE_HINT_ARCHIVE"
cd ..
```

Архив приватный, не зашифрован, в Git его добавлять нельзя. При отказе архиватора
сохраните ошибку и разберите незавершённое состояние; не сбрасывайте recovery gate.

Примените патч из корня репозитория:

```bash
git apply "$BUBLIK_LANG_V3_DIR/bublik-languages-fix-v3.patch"
cd day-30-private-ai-service
python -c 'from bublik_service import __version__; from bublik_service.languages import POLICY; print(__version__, POLICY)'
python scripts/verify_report.py reports/verified/languages-policy-v3-offline-final-20261011.json
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Ожидаются **0.10.2 reply-language-v3** и совпадающий source guard. Если guard
не совпал, не удаляйте отчёты: проверьте перечисленные исходники, включая два
диагностических scripts. Новый init-db, перенос пользователя и новая база не нужны.
Caddy/Tailscale/Ollama не требуется перенастраивать. Readiness должна показывать
совпадающий runtime manifest и `runtime_source_unchanged: true`.

## Проверка через API и устройства

```bash
BUBLIK_LANG_V3_CHECK="$(mktemp -d "$HOME/bublik-language-v3-check.XXXXXX")"
python scripts/check_languages_live.py \
  --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_LANG_V3_CHECK/live.json"
python scripts/verify_report.py "$BUBLIK_LANG_V3_CHECK/live.json"
```

Четыре генерации: RU и EN, по первому вопросу без RAG и продолжению с RAG.
Checker проверяет противоположное языковое пожелание в вопросе, arithmetic
control, completion, v3/hint hashes и сохранность исходного пользовательского
текста в истории. Настройки аккаунта не меняет. Поиск и полная смысловая
правильность языка этим ограниченным набором не доказаны.

В браузере: русский интерфейс / English replies, новый диалог, русский вопрос
«Привет! Расскажи в двух предложениях, чем ты можешь помочь». Затем следующий
русский вопрос с включённым RAG. Ожидаются английские ответы с «Ответ сохранён»
на Mac, Android и iPhone. Переключите replies на русский, задайте английский
вопрос: следующий ответ русский; старые сообщения остаются прежними.

Offline report проверяет хранение, отправку HTTP, hashes, границу бюджета и
совместимость с synthetic inference. Он не является доказательством поведения
реальной Qwen или проверки телефонов. Старые отчёты соответствуют прежним
исходникам и сохранены; текущий source guard должен сверяться с новым отчётом.
