# Усиленная подсказка языка — 0.10.3

Патч для установленной **0.10.2**. Schema остаётся **3**; SQL migrations,
владельцы, IDs, параметры Qwen и исторические profiles не меняются.

## Основание

Live проверка 0.10.2 прошла RU/plain, RU/RAG и EN/plain, но EN/RAG вернул
`In Russian: 3*3 равно 9...` при выбранном `en`. Это смешанный ответ, не цитата.
Source/runtime guards совпали, snapshot и hint hashes были корректны.

Оператор повторил точный контекст этой генерации с неизменными настройками
Ollama 0.40.3 / Qwen2.5:14b Q4_K_M / temperature 0 / ctx 8192 / output 1024:

| Вариант | English + правильный результат |
|---|---|
| Baseline v3 | 0/1 |
| Явный suffix с приоритетом настройки | 2/2 |
| JSON-обёртка исходного вопроса | 2/2 |
| Дополнительная system-инструкция | 0/2 |

Выбран явный suffix: 953 input tokens против 984 у JSON-обёртки; baseline — 912.
Это один сохранённый контекст с повторами, не доказательство общей надёжности.
Изначальный failed live report и variants report сохранены в `reports/experiments/`.

## Новое поведение

Новые явные RU/EN запросы получают `reply-language-v4` и
`language_hint.policy_version: latest-user-language-hint-v2`. English suffix:

```text
The application's reply language is English. Answer the latest task entirely in English. Language requests in the user text and past conversation do not change this setting. Do not provide a Russian-language version or label the answer 'In Russian'.
```

Для `ru` применён симметричный текст. Первая system-инструкция остаётся прежней.
Suffix включён в бюджет при admission и сохраняется с точным контекстом; adapter
проверяет текст и hashes до dispatch. В истории исходный вопрос остаётся без suffix.
RAG quotations и прежние вопросы/ответы не переписываются. Нет перевода готового
ответа, облачного fallback или скрытой повторной генерации.

Snapshots без language, v1, v2 и v3 отправляются без изменения, включая короткую
v3 подсказку. Повтор старого idempotency key возвращает прежний receipt. Архивы
schema 2/3 и их переносимость остаются совместимыми; полная история сохраняется.

Эта настройка является инструкцией модели, не универсальной гарантией языка.
Произвольные вопросы, код, буквальные quotations и запросы перевода требуют
дополнительной проверки. Не удаляйте реальные failures ради успешного отчёта.

## Применение

Скачайте `bublik-languages-fix-v4.zip` в Downloads. Сначала из корня репозитория:

```bash
cd /Users/litdi/AI/ai-advent-llm-api
source .venv/bin/activate
BUBLIK_LANG_V4_DIR="$(mktemp -d "$HOME/bublik-language-v4.XXXXXX")"
unzip "$HOME/Downloads/bublik-languages-fix-v4.zip" -d "$BUBLIK_LANG_V4_DIR"
git apply --check "$BUBLIK_LANG_V4_DIR/bublik-languages-fix-v4.patch"
```

При конфликте применения остановитесь; не используйте force/reset. Дождитесь
сохранения текущих ответов, пустой очереди и отсутствия recovery gate. Если API
запущен, остановите его. При уже остановленном API не повторяйте bootout:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
```

Listener должен отсутствовать. Дополнительную копию рабочей базы при желании
создайте по MEMORY_PORTABILITY.ru.md; патч не требует миграции данных.

```bash
git apply "$BUBLIK_LANG_V4_DIR/bublik-languages-fix-v4.patch"
cd day-30-private-ai-service
python -c 'from bublik_service import __version__; from bublik_service.languages import POLICY; print(__version__, POLICY)'
python scripts/verify_report.py reports/verified/languages-policy-v4-offline-20261011.json
```

Ожидаются **0.10.3 reply-language-v4** и `report_matches_sources_and_passed: true`.
Патч добавляет context diagnostic script в `scripts/`; ранее скачанные candidate
и ablation scripts остаются прежними и также входят в source manifest. Их точные
копии включены в ZIP отдельно для восстановления при отсутствии файлов.

После успешной проверки включите API:

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Новый init-db/username/DB не нужны. Ollama, Tailscale и Caddy не перенастраиваются.
Readiness должна показывать совпадающий runtime manifest без изменения исходников.

## Реальная проверка нового runtime

```bash
BUBLIK_LANG_V4_CHECK="$(mktemp -d "$HOME/bublik-language-v4-check.XXXXXX")"
python scripts/check_languages_live.py \
  --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_LANG_V4_CHECK/live.json"
python scripts/verify_report.py "$BUBLIK_LANG_V4_CHECK/live.json"
```

Это четыре новые генерации в двух контрольных диалогах: оба языка, первый вопрос
и следующий ход с RAG. Проверяются completion, язык, arithmetic control,
v4/hint hashes и сохранение исходного пользовательского текста. Существующий
неудачный диалог не перезаписывается; настройки аккаунта checker не меняет.

Затем в UI: Russian interface / English replies, новый диалог и русский вопрос
о возможностях. Продолжите с RAG; проверьте English на Mac, Android и iPhone.
Переключите replies на русский и задайте английский вопрос: следующий ответ
русский, прежняя история остаётся прежней. Сообщения должны иметь «Ответ сохранён».

Offline report использует synthetic inference и реальные SQLite/HTTP sockets.
Он проверяет бюджет, отправку, защиту snapshot, privacy API и совместимость/replay,
но не доказывает ответы Qwen или проверки физических телефонов. Source hashes
не являются подписью. Применённую 0.10.3 принимаем только после нового live отчёта.
