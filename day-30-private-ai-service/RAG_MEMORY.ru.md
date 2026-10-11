# Бублик — RAG по истории, первый этап (0.9.1)

> Текущая версия — 0.10.0, schema 3: [RU/EN и обновление](LANGUAGES.ru.md).
> Ниже сохранены инструкции первоначального RAG 0.9.1 / schema 2.
> Для обновления действующей установки используйте новый guide; не применяйте
> старый RAG-пакет поверх schema 3 и не откатывайте рабочий код к 0.9.1.

Это расширение после принятого дня30. Первый этап сохраняет источник каждого
переданного модели фрагмента; полная история остаётся независимым оригиналом.
Веб-чат включает поиск по умолчанию; его можно отключить вручную. Автоматическое извлечение/обновление фактов,
семантические embeddings, голос и автономные инструменты не добавлены.

## Что реализовано

Сообщение с `use_memory=true` → авторизация и проверка повтора → готовность Qwen →
FTS5-поиск по обеим сторонам своей прошлой переписки → бюджет контекста →
повторная проверка источников в транзакции → сохранённый snapshot → очередь →
Qwen → сохранённый ответ и источники на всех устройствах.

- Web UI передаёт use_memory=true по умолчанию. API v1 без поля сохраняет false
  и прежние idempotency fingerprints; явное отключение доступно в Web UI.
- RAG использует recent-complete-pairs-memory-v1 / history-fts-v2. Полный текст
  system prompt private-chat-v2 не переписывается; отдельная инструкция памяти
  и JSON с архивными цитатами сохраняются в inference snapshot.
- Индексируются все сохранённые user messages и непустые terminal assistant
  messages: completed, truncated, failed, interrupted. Источник содержит role/status.
  Assistant guesses не объявляются фактами пользователя; partial явно помечается.
  Queued/running assistant text ещё меняется и входит только в обычную историю;
  после terminal event он становится searchable. Пустые ответы остаются в истории.
- Для каждого owner отдельный приватный SQLite cache в `memory-index/` рядом с
  рабочей базой. Папка0700, файл0600; symlinks/неприватные файлы отвергаются.
- Индекс обновляется по зафиксированным chat events; checkpoint и изменения
  index атомарны. Completion после предыдущего поиска не теряется. Неудачная
  индексация не пишет сообщения в основной базе и не переключает на обычный чат.
- На процесс одна операция поиска одновременно, ожидание lock до1s; SQLite
  операции имеют deadline10s. Индексация идёт по строкам, без загрузки всей истории
  в Python list. Большие индексы требуют последующих замеров и отдельного tuning.
- Нет bge-m3/embedding-запросов: действующее ограничение одной загруженной Qwen
  остаётся. Это не измерение экономии RAM и не сравнение с vector retrieval.

Поиск lexical: Unicode слова, prefix queries, BM25. Из запроса берутся до12
различных слов (до64 символов), RU/EN stop words убираются; для русских слов от7
букв используется простой prefix без последних двух букв. Это эвристика, не
полноценная морфология. OR-кандидаты ранжируются; до24 chunks рассматриваются,
возвращается до3 разных сообщений. Индекс не смешивает слова/BM25 других owners.
Нет semantic threshold или гарантии, что любой найденный fragment релевантен.
Вопросы и ответы ассистента тоже находятся в raw index; это не извлечённые факты,
и повторяющиеся вопросы могут создавать поисковый шум. Fact extraction/curation
потребует отдельного этапа; сейчас всё остаётся проверяемой исходной перепиской.

Chunks перекрываются на80 символов, чтобы слова до64 символов на границе не терялись.
Цитаты до800 UTF-8 bytes, точные character offsets и SHA-256 полного исходного
сообщения. В контексте до3 источников; весь блок памяти до2600 консервативных
input tokens. Общий предел8192 включает1024 output и512 margin. Последний вопрос
обязателен; recent complete pairs заполняют оставшийся budget. Часть найденных
источников может не войти в context. Полная история от этого не удаляется.

## Ограничения качества и безопасность

Не найдено ≠ никогда не говорили. Поиск по словам может пропустить синонимы,
перефразировки и фрагменты с другой формулировкой. Он может вернуть нерелевантный
текст с общим словом. В UI показываются **источники контекста**, не автоматический
сертификат правдивости ответа. Ответ модели требует отдельной проверки.

Архивные сообщения — недоверенные данные. Модель получает отдельную instruction
не выполнять команды внутри цитат и не придумывать отсутствующую память.
Это снижение риска prompt injection, не доказательство полного иммунитета Qwen.
Инструментов/сетевых действий у модели нет; owner isolation проверяется сервером,
не поручается модели. Противоречащие сообщения сохраняются отдельно с датами,
не переписываются в один автоматически объявленный факт.

Пустой поиск сохраняет explicit memory mode с пустым archive. Ошибка index даёт
503 без admission/fallback. Повтор с тем же ключом возвращает прежний receipt
без нового поиска; изменение use_memory для такого ключа —409. Новый retry может
выбрать режим заново. Checkbox возвращается к true при reload/logout и не пишется в storage.
Источники уже сохранённых ответов продолжают отображаться после reload.

История и index содержат личные данные, архивы пока plaintext. Доступ через
существующие HTTPS, cookie/bearer auth, owner authorization, Origin/CSRF и quotas.
`POST /api/v1/memory/search` хранит query в JSON, не URL. Логи по-прежнему не
записывают личные prompts/ответы. См. [API.md](API.md).

## Сохранённые проверки реализации

Итоговый прогон **198/198** (161 прежняя regression +37 RAG checks), без failures,
errors/skips: Linux x86_64, Python3.13.16, SQLite3.53.1, см. elapsed_seconds в отчёте.
Отчёт [rag-memory-v2-offline-20261011.json](reports/verified/rag-memory-v2-offline-20261011.json)
содержит74 source hashes. Проверены owner isolation, CSRF/scopes, source hashes,
повторы, context budget, роли/статусы и partial text, running exclusion,
original-context access, отсутствие age cutoff, сменный backend, concurrent search, deadline,
cache tampering, quotes на Unicode boundaries и архив/restore с rebuilding index.
Предварительные184/184,187/187 и188/188 сохранены отдельно как предыдущие исходники.
JS syntax проверен Node; настоящий браузер, реальная Qwen и телефоны на0.9.1
здесь не испытаны. Не переносите live-качество0.8.0 на новый RAG без проверки.

## Обновление существующего Mac

Поставка `bublik-rag-memory-v2.zip` содержит Git patch к main
`ce8952ca930c4ebb5aea4c9ff537c97f73757a66`. Не заменяйте папки через Finder.
Git применяет изменения к файлам проекта; рабочая база находится отдельно.

Сначала распаковка и проверка, пока чат продолжает работать:

```bash
cd /Users/litdi/AI/ai-advent-llm-api
source .venv/bin/activate
BUBLIK_RAG_INSTALL="$(mktemp -d "$HOME/bublik-rag-install.XXXXXX")"
unzip "$HOME/Downloads/bublik-rag-memory-v2.zip" -d "$BUBLIK_RAG_INSTALL"
git --no-pager status --short --untracked-files=all
git apply --check "$BUBLIK_RAG_INSTALL/bublik-rag-memory-v2.patch"
```

Ожидается чистый checkout и успешный check без вывода. При конфликте не используйте
`--reject`, не удаляйте файлы и не делайте reset: сначала выясните отличия. Если
архив скачан с другим именем, замените только его путь в unzip.

Дождитесь сохранения всех ответов и прекратите новые отправки со всех устройств:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
cd day-30-private-ai-service
BUBLIK_RAG_DB="/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3"
python -m bublik_service --db "$BUBLIK_RAG_DB" storage-status
```

Нет listener8000; integrity ok, queued/running0, recovery_required=false.
Если API уже остановлен, повторный bootout не нужен. Сделайте свежий idle archive:

```bash
BUBLIK_RAG_ARCHIVE="$HOME/bublik-memory-archives/pre-rag-$(date +%Y%m%d-%H%M%S)"
python scripts/memory_archive.py create --db "$BUBLIK_RAG_DB" --output "$BUBLIK_RAG_ARCHIVE"
python scripts/memory_archive.py verify --archive "$BUBLIK_RAG_ARCHIVE"
```

Ожидается verified/restorable_now=true. Каталог архива заранее не создавайте.
Теперь примените проверенный patch:

```bash
cd ..
git apply "$BUBLIK_RAG_INSTALL/bublik-rag-memory-v2.patch"
cd day-30-private-ai-service
python -c 'from bublik_service import __version__; print(__version__)'
BUBLIK_RAG_CHECK="$(mktemp -d "$HOME/bublik-rag-check.XXXXXX")"
python -W error::ResourceWarning scripts/check_storage.py --output "$BUBLIK_RAG_CHECK/offline.json"
python scripts/verify_report.py "$BUBLIK_RAG_CHECK/offline.json"
python scripts/verify_report.py reports/verified/rag-memory-v2-offline-20261011.json
```

Ожидается версия0.9.1, passed без skips, оба hash verifiers true. Исторические
JSON относятся к прежним исходникам: их guard сейчас может не совпасть, это
не основание их переписывать. Новые зависимости сервера не нужны; Python3.13.

Только после успешной проверки запустите прежний LaunchAgent на прежней базе:

```bash
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Если проверки не прошли, сохраните вывод. Если новый API ещё не запускался и
новых jobs нет, можно проверить `git apply --check -R <patch>`, отменить этот patch
через `git apply -R <patch>` из корня и запустить прежний LaunchAgent на прежней
базе. Не используйте reset и не восстанавливайте snapshot поверх новых данных.
Не запускайте прежнюю версию поверх новых queued RAG jobs. Схема остаётся2,
но старый интерфейс не умеет отображать новые citations. Не восстанавливайте
pre-rag snapshot поверх рабочей базы: он не содержит последующих сообщений.

## Реальная Qwen и телефоны

Откройте тот же HTTPS чат и обновите страницу/PWA на всех устройствах.
Проверьте наличие нового checkbox: он включён сразу после открытия. Для воспроизводимой RU/EN проверки:

```bash
python scripts/check_rag_live.py \
  --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_RAG_CHECK/live.json"
python scripts/verify_report.py "$BUBLIK_RAG_CHECK/live.json"
```

Checker сначала сравнивает работающий runtime с локальными файлами. Он создаёт
четыре новых контрольных чата (две исходные записи, два независимых recall чата),
использует уникальные synthetic project/device names и проверяет exact answer,
правильную source label, original source endpoint, поиск ответов ассистента с role/status,
окружающий исходный разговор, сохранённые citations и
negative retrieval. В JSON IDs/hashes/metrics; личные ответы/токен не экспортируются.
Повторный запуск требует нового output пути; не затирайте failed report.

Отдельно на телефоне: откройте RAG recall чат, проверьте «Ответ сохранён», раскройте
источники и перейдите по ссылке. На Mac должны быть те же ответ/citations. Источник
старше последней страницы открывается в отдельном source preview, не нарушая
pagination. Перезагрузите API штатно, вновь откройте ответ: history и citations
остаются. Это отдельная ручная приёмка, не доказанная fixture.

## Дополнительная проверка интерфейса

```bash
python -m pip install -r requirements.browser.lock
python -m playwright install chromium
python scripts/check_rag_ui.py --output "$BUBLIK_RAG_CHECK/browser.json"
python scripts/verify_report.py "$BUBLIK_RAG_CHECK/browser.json"
```

Chromium mobile viewport / TLS / реальный API+SQLite, synthetic engine. Проверяет
checkbox, сохранённые sources, старый source link, literal HTML quotes, logout,
отсутствие external requests и web storage. Не доказывает Qwen/физический телефон.
В среде подготовки Chromium отсутствовал; этот browser check **не пройден** здесь.

## Архив и перенос

Основная схема2 и migrations не изменяются. Старые архивы0.8.0 читаются; новые
RAG snapshots входят в обычный SQLite archive. Cache `memory-index/` не входит,
после restore строится по исходным chat events. Удаление только cache при
остановленном API не удаляет память; не трогайте рабочий `chats.sqlite3`/WAL/SHM.
Новые SQL tables не добавлены в основной DB. IDs/users/passwords сохраняются;
browser sessions и API tokens сбрасываются только в восстановленной копии.

[Архитектура непрерывной памяти](MEMORY_ARCHITECTURE.ru.md) фиксирует разделение
оригиналов, индекса, будущих summaries/facts и inference context. Сменный backend
HistorySearch не меняет авторизацию источников или сохранённые IDs.

Следующие этапы: semantic retrieval с отдельным ресурсным профилем; версионируемые
факты/предпочтения с подтверждением и исправлениями; контроль противоречий;
зашифрованные off-host copies и physical transfer. Исходная переписка не заменяется
summary или embeddings. [BACKLOG.ru.md](BACKLOG.ru.md).

Основание lexical backend: [SQLite FTS5 documentation](https://www.sqlite.org/fts5.html).
