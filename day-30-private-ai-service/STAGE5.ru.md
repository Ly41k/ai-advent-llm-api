# Этап 5 — адаптивный Web UI

Этапы 1–4 приняты на MacBook. Реализован браузерный чат на существующем API v1:
вход/выход, несколько диалогов, последние сообщения и более ранние страницы,
открытие по сохранённой ссылке, SSE snapshots, polling fallback и явные повторы.
Ollama/profile/SQLite schema не менялись: schema=2, Qwen2.5:14b Q4_K_M,
8192 context / 1024 output / temperature=0. Предыдущие дни не менялись.

LAN и телефон через мобильный интернет — следующий этап 6. В этом этапе сервер
по-прежнему слушает только 127.0.0.1. Не подставляйте этот localhost URL на телефоне:
он означает сам телефон. Viewport Chromium не доказывает доступ с устройства.
PWA, launchd/reboot, финальная нагрузка — последующие этапы. Backup operations
и перенос старой истории отложены по вашему решению до полной реализации.

## 1. Обновление

Остановите API через Ctrl-C. Полный `day30-stage5.zip` распаковывается в корень
репозитория с объединением каталога дня 30, без удаления .venv/личных файлов.
Не заменяйте папку `scripts` отдельной неполной папкой. Базы, токены, TLS keys
и пользовательские `reports/check` в архив не входят.

Если архив скачан в Downloads:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
BUBLIK_UPDATE_DIR="$(mktemp -d)"
unzip "$HOME/Downloads/day30-stage5.zip" -d "$BUBLIK_UPDATE_DIR"
ditto "$BUBLIK_UPDATE_DIR/day-30-private-ai-service" .
python -m pip install -e .
python -c 'import bublik_service; print(bublik_service.__version__)'
```

Ожидается `0.4.0`. Backend не требует Node/npm, frontend build или Playwright.
Для перехода 0.3.0→0.4.0 нет новой SQL-миграции; используется та же база schema=2.

## 2. Запуск с уже проверенными базой и сертификатом

Активируйте .venv в терминале и перейдите в каталог дня 30:

```bash
BUBLIK_STAGE4_DIR="/Users/litdi/bublik-day30-stage4.V1EM3F"
python -m bublik_service --db "$BUBLIK_STAGE4_DIR/chats.sqlite3" \
  serve --port 8443 \
  --tls-cert "$BUBLIK_STAGE4_DIR/tls/cert.pem" \
  --tls-key "$BUBLIK_STAGE4_DIR/tls/key.pem"
```

Ollama должна работать на localhost, другие модели/клиенты не должны занимать
engine. Не запускайте второй API worker или terminal chat с той же базой.
Если семидневный сертификат истёк, создайте новую пару по пункту 5 STAGE4.ru.md
в новом каталоге, затем явно используйте новые пути. Проверку TLS не отключайте.

Откройте **https://localhost:8443/** на Mac. Для обычного браузера сначала
нужно доверить ваш временный localhost-сертификат. Добавьте `tls/cert.pem`
в пользовательскую «Связку ключей» и установите доверие для SSL. Через терминал:

```bash
security add-trusted-cert -r trustRoot \
  -k "$HOME/Library/Keychains/login.keychain-db" \
  "$BUBLIK_STAGE4_DIR/tls/cert.pem"
```

macOS может запросить системное подтверждение. Добавляйте только сертификат,
который создали сами в этапе 4; private `key.pem` остаётся приватным файлом.
После проверки временное доверие можно удалить через «Связку ключей».
LAN/устойчивые сертификаты будут настроены отдельно на этапе 6.

Войдите как `yuriy` с ранее установленным паролем. Старые тестовые диалоги
этого пользователя доступны сразу. API-токен в браузер вводить не требуется.

## 3. Ручная проверка на Mac

1. Создать диалог, отправить обычный вопрос, дождаться статуса «Ответ сохранён».
2. Задать уточняющий вопрос со ссылкой на предыдущий ответ; проверить смысл.
3. Создать второй диалог; убедиться, что его история независима.
4. Перезагрузить страницу: тот же диалог из `#chat=...` и история открываются снова.
5. Открыть ту же ссылку в другом браузере/отдельном профиле, войти тем же username,
   продолжить диалог и нажать ↻ в первом браузере. Два профиля дают независимые cookie.
6. Остановить/запустить API с той же базой; открыть прежнюю ссылку. Успешно
   сохранённые сообщения остаются. Reload и subscriber disconnect не повторяют inference.
7. В Chrome responsive mode проверить ширины 390 и 320 px, меню диалогов,
   длинный текст, перенос строки и прокрутку. На desktop Enter отправляет,
   Shift+Enter даёт перенос; на touch-устройствах Enter даёт перенос, отправка кнопкой.
8. Выйти: список, тексты сообщений и черновик исчезают. Войти другим username:
   чужие диалоги недоступны. Реальные Safari/мобильная клавиатура ещё требуют проверки.

Модель выдаёт plain text, включая Markdown/HTML буквально. Это защищает от HTML
из ответов; форматирование Markdown/code blocks — отдельное будущее улучшение.

## 4. Автоматические проверки

Обычные тесты не требуют браузера:

```bash
python -W error::ResourceWarning scripts/check_storage.py
python scripts/verify_report.py reports/verified/stage5-offline.json
```

Браузерные зависимости нужны только для тестов, не для работы сервера:

```bash
python -m pip install -r requirements.browser.lock
python -m playwright install chromium
python scripts/check_web_ui.py
```

Последняя команда запускает **отдельный временный** loopback TLS API, реальную
SQLite и синтетический engine. Ваш сервер/база/Ollama не используются. Проверяет
SSE/polling, потерянное подтверждение POST и replay с прежним ключом, два профиля,
409 при конкурентном изменении, failed retry без второй user question, quota/UTF-8/
context errors, 120-message pagination, HTML safety, revocation/logout, отсутствие
external requests/localStorage/sessionStorage и мобильные ширины. Не доказывает Qwen.

Скрипт делает certificate-verified HTTPS preflight. Chromium доверяет только SPKI
временного сертификата через scoped launch option, глобального ignore HTTPS нет.
Это не проверка доверия вашего обычного браузера через Keychain.
`--screenshots NEW_DIR` разрешён только здесь: все данные fixture синтетические.

## 5. Автоматический Web UI + настоящая Qwen на Mac

Ваш HTTPS API из пункта 2 должен работать. Во втором терминале:

```bash
BUBLIK_STAGE4_DIR="/Users/litdi/bublik-day30-stage4.V1EM3F"
python scripts/check_web_ui_live.py --username yuriy \
  --ca-file "$BUBLIK_STAGE4_DIR/tls/cert.pem" \
  --output "$BUBLIK_STAGE4_DIR/web-ui-live-$(date +%Y%m%d-%H%M%S).json"
```

Пароль запрашивается скрыто; он не находится в argv, отчёте или browser storage.
Скрипт создаёт отдельный синтетический контрольный диалог, проверяет три настоящих
multi-turn ответа: запоминание слова на desktop, продолжение через вторую browser
session с mobile viewport, возврат на desktop. Проверяет reload, SSE, cookie,
logout, runtime hashes, отсутствие внешних запросов. Ответы в отчёте только SHA-256.
Неверный контрольный ответ — failed, а не «технически passed».
Для сравнения runtime source скрипт запускается из актуального checkout.

Это реальный браузер+Qwen, но обе сессии работают на Mac: физический телефон,
Safari/iOS/Android, LAN и mobile internet этим отчётом не подтверждаются.
Не запускайте параллельно другие check harness: они разделяют owner quota и engine.

## 6. Повторы, ограничения и приватность

- Неопределённый результат POST сохраняет исходные payload/revision/key в памяти
  вкладки. Кнопка «Повторить доставку» посылает именно его, без автоматического retry.
  Не путать с повтором **неудачной генерации**: новый attempt того же user message.
- При 409 история обновляется, черновик остаётся: сначала прочтите изменения,
  затем явно отправьте его снова. При 422/429 черновик также остаётся.
- До подтверждения доставки нельзя менять исходный payload. Отмена повтора
  сначала читает историю; сервер мог уже принять запрос.
- После reload/закрытия вкладки черновики и неопределённый запрос не сохраняются
  в браузерном хранилище и не пересылаются автоматически. Сначала проверьте
  серверную историю. При уходе с черновиком/неопределённым POST браузер предупреждает.
- SSE заменяет persisted snapshot по message ID/stream revision. При ошибке
  используется GET каждые 5 s, не накопление текста и не повтор inference.
- Background tab закрывает SSE; возврат обновляет auth/history. Model readiness
  проверяется раз в 30 s; новые сообщения другого устройства — раз в 15 s либо ↻.
  История доступна при outage, новая отправка отключена до готовности модели.
- Полная история в SQLite не сокращается. UI сначала получает 50 последних
  сообщений, остальные загружает по кнопке. Окно модели отдельно; UI показывает
  `omitted_turns` при новой генерации. Max output и terminal errors видимы.
- Все ресурсы локальны, нет CDN/analytics/service worker. Cookie HttpOnly/Secure/
  SameSite=Strict; CSRF в памяти. Все ответы no-store; UI CSP разрешает только
  свои JS/CSS/connect, API сохраняет прежний default-src none.

## Что отправить

`web-ui-live-*.json` и краткий результат ручного desktop/Safari/restart сценария.
Не присылайте пароль, token JSON, cookie, private key или рабочую SQLite.
Полный итог и ограничения: [VALIDATION.stage5.ru.md](VALIDATION.stage5.ru.md).
