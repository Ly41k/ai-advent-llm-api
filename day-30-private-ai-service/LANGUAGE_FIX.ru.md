# Исправление языка ответа — 0.10.1

Для уже установленной **0.10.0**. Схема базы остаётся **3**: новых SQL migrations
нет. Патч накладывается на установленное RU/EN обновление, включая ещё не
закоммиченные файлы. Не применяйте его к 0.9.1 напрямую.

## Причина и исправление

Оператор проверил три сохранённых запроса: настройка и snapshot содержали `en`,
но реальные ответы были русскими. Доставка настройки работала. В исходниках
обнаружен конфликт: основной prompt требует язык пользователя, дополнительный
system message — язык настройки. Это правдоподобная причина наблюдаемого поведения;
исправление и фактический ответ Qwen проверяются отдельно.

Новые явные RU/EN запросы используют `reply-language-v2`: в первой системной
инструкции нет требования отвечать на языке входного сообщения. Она однозначно
задаёт выбранный язык и приоритет над противоположным языковым пожеланием
вопроса. Код/имена/буквальные цитаты и явно запрошенные переводы допускаются.
Не используется автоматическая перегенерация или облачный переводчик.

Исторические profiles `private-chat-v1/v2` не переписаны. Snapshot нового запроса
сохраняет эффективный system text и версию языковой политики; он учитывается в
контекстном бюджете. RAG quotes и исходный вопрос остаются прежними.
Старые snapshots `reply-language-v1`, ответы, IDs и receipts сохраняются.
Повтор прежнего idempotency key возвращает прежний результат, не исправляет
старый ответ новой генерацией. Inference adapter проверяет новые roots и умеет
отправить прежний v1 snapshot без изменения. API без reply_language сохраняет
прежнее поведение. Устанавливаемые RU/EN настройки и архивы schema 3 совместимы.

## 1. Проверить патч

Скачайте `bublik-languages-fix-v2.zip` в Downloads:

```bash
cd /Users/litdi/AI/ai-advent-llm-api
source .venv/bin/activate
BUBLIK_LANG_FIX_DIR="$(mktemp -d "$HOME/bublik-language-fix.XXXXXX")"
unzip "$HOME/Downloads/bublik-languages-fix-v2.zip" -d "$BUBLIK_LANG_FIX_DIR"
git apply --check "$BUBLIK_LANG_FIX_DIR/bublik-languages-fix-v2.patch"
```

При ошибке применения остановитесь и разберите отличия; не используйте force,
не откатывайте RU/EN обновление и не сбрасывайте рабочие изменения через git reset.

## 2. Остановить API и сохранить текущую базу

Закончите отправки на всех устройствах, дождитесь «Ответ сохранён» и idle:
queued/running 0, recovery_required false. Затем в той же вкладке терминала:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
cd day-30-private-ai-service
BUBLIK_DB="/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3"
BUBLIK_PRE_FIX_ARCHIVE="$HOME/bublik-memory-archives/pre-language-fix-$(date +%Y%m%d-%H%M%S)"
python scripts/memory_archive.py create --db "$BUBLIK_DB" --output "$BUBLIK_PRE_FIX_ARCHIVE"
python scripts/memory_archive.py verify --archive "$BUBLIK_PRE_FIX_ARCHIVE"
```

Listener должен отсутствовать, create/verify — пройти, restorable_now=true.
Архив приватный, но не зашифрован; не добавляйте его в Git. Caddy/Serve/Ollama
не требуется останавливать или перенастраивать.

## 3. Применить исправление и запустить

```bash
cd ..
git apply "$BUBLIK_LANG_FIX_DIR/bublik-languages-fix-v2.patch"
cd day-30-private-ai-service
python -c 'from bublik_service import __version__; print(__version__)'
python scripts/verify_report.py reports/verified/languages-policy-v2-offline-20261011.json
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Ожидаются 0.10.1 и совпадающий source guard. Проверьте readiness и runtime hashes
по RUNBOOK: запущенный сервер должен использовать новый код. Schema остаётся3;
init-db, новая база или перенос владельца для этого исправления не требуются.

## 4. Проверить реальные ответы

Повторно откройте чат на Mac и телефонах. Русский UI + English replies:

1. Создайте контрольный диалог. Отправьте по-русски: «Привет! Расскажи в двух
   предложениях, чем ты можешь помочь». Ожидается английский ответ.
2. Отправьте второй русский вопрос в том же диалоге с включённым поиском истории.
   Ответ также должен быть английским; история видна на телефонах.
3. Переключите replies на русский, задайте английский вопрос. Ожидается русский
   ответ. Прежние английские сообщения должны остаться английскими.

Для нового JSON-отчёта используйте новый каталог:

```bash
BUBLIK_LANG_FIX_CHECK="$(mktemp -d "$HOME/bublik-language-fix-check.XXXXXX")"
python scripts/check_languages_live.py \
  --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_LANG_FIX_CHECK/live.json"
python scripts/verify_report.py "$BUBLIK_LANG_FIX_CHECK/live.json"
```

Checker создаёт два контрольных диалога: для каждого языка обычный ход и
следующий ход с RAG (всего четыре генерации). Проверяет язык при противоположной
инструкции в вопросе, snapshot v2, сохранность входа и completion. Сохраняет
метрики/IDs/хеши без текста; настройки владельца не меняет. Это ограниченный
контроль, не гарантия для произвольных ответов и не проверка semantic retrieval.
При status failed сохраните JSON и сообщите результат; прежние отчёты не удаляйте.

Offline report использует реальные SQLite/HTTP sockets, но synthetic engine.
Проверены новые инструкции, их отправка adapter, отказ при повреждении root/policy,
совместимость v1 и неизменность старых snapshots/replay. Реальная Qwen,
Chromium/Safari и физические RU/EN устройства в среде подготовки не запускались.
Хеши отчёта не являются подписью или доказательством live model behavior.
