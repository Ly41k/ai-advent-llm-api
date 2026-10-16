# Этап 3 — Project RAG на Mac

Из корня repo, в установленном Python 3.13 окружении. Dependencies прежние.
Doctor 0.1.2 подтвердил day30_off=true, launchd disabled=true/loaded=false,
отсутствие процессов и listener на 8000. Приватный чат оставляем отключённым.

## FTS5 без модели

```bash
python day-31-developer-assistant/main.py index build --mode fts
python day-31-developer-assistant/main.py index verify
python day-31-developer-assistant/main.py search "Как устроена память Бублика?" --mode fts --final-k 3
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage3.py --output /tmp/day31-stage3-mac.json
```

Expected: built → verified → retrieved; 40 docs / 376 chunks при стандартном
корпусе и settings; 78 tests в v0.2.3. Локальные изменения docs могут изменить counts.
semantic_support_verified=false нормально: Qwen ещё не генерирует ответы.

State по умолчанию находится вне repo:
~/Library/Application Support/BublikDeveloper/ai-advent-llm-api.
Старые версии сохраняются. Stale index не публикует устаревшие excerpts.

## Подготовить embedding model

Ollama должна быть запущена. Проверить модель через ollama list.
Если bge-m3 отсутствует, скачать до prepare:

```bash
ollama pull bge-m3
```

Закончить pull до model session. Не запускать Revik/другие Ollama clients
во время выделенной сессии. Lease контролирует day31 processes, но не
произвольного стороннего клиента того же OS user.

## Свежая сессия без предположения об idle

```bash
python day-31-developer-assistant/main.py models prepare
```

Prepared сохраняет OS epoch текущего listener, без inference. Полностью
завершить и снова открыть Ollama. Для desktop app через терминал:

```bash
osascript -e 'tell application "Ollama" to quit'
open -a Ollama
```

Для ручного ollama serve: остановить его Ctrl+C в исходном терминале и снова
запустить там ollama serve. Не создавать второй сервер. Дождаться готовности:

На Mac пользователя выход через AppleScript возвращал `User cancelled (-128)`,
а обычный перезапуск приложения сохранял процесс сервера. Для полного
перезапуска выделенной сессии с завершёнными другими Ollama clients:

```bash
killall -TERM -u "$(id -un)" Ollama
killall -TERM -u "$(id -un)" ollama
```

Подождать завершения (обычно 3–5 секунд), затем `open -a Ollama`.
`No matching processes` означает, что соответствующий процесс уже остановлен.
Не повторять prepare после остановки: confirm сравнивает новый процесс с
сохранённым ранее epoch. Такой перезапуск подтверждён пользователем на Mac.

```bash
python day-31-developer-assistant/main.py models confirm
```

Confirmed требует новый epoch и отсутствие old orphan runner. Если epoch не
изменился — model_session_required. Doctor отдельно продолжает показывать
ollama_idle_verified=false: его scope — day30, не fresh session protocol.

## Реальные bge-m3 и hybrid

```bash
python day-31-developer-assistant/main.py index build --mode hybrid
python day-31-developer-assistant/main.py index verify
python day-31-developer-assistant/main.py search "How does memory retrieval work?" --mode dense --final-k 3
python day-31-developer-assistant/main.py search "Как устроена память Бублика?" --mode hybrid --final-k 3
```

Build может занять несколько минут: batches по 8, последовательно.
376 chunks требуют 47 embedding calls. Digest модели и dimension=1024
сохраняются в metadata; vectors хранятся float32. Финальный batch/query
использует keep_alive=0s. Никаких дополнительных копий Qwen.

Перед dispatch сохраняется uncertain checkpoint. При потерянном ответе,
timeout или crash автоматического retry нет. Recovery:
prepare → restart Ollama → confirm. Если old uncertain epoch уже сохранён,
confirm после проверяемого restart также может восстановить сессию.
SESSION.json вручную не редактировать.

## Retrieval comparison

```bash
python day-31-developer-assistant/scripts/compare_project_retrieval.py --modes all --output /tmp/day31-retrieval-all-mac.json
```

12 calibration cases, одинаковый corpus/K, последовательные FTS/dense/hybrid.
Dense и hybrid делают отдельные query embedding calls, учтённые в отчёте.
Это не Qwen answer quality и не final held-out golden set. Negative candidates
могут показать, что стартовый порог недостаточен; такие failures сохраняются.
FTS-only calibration: --modes fts. Output paths должны быть новыми.

## Explicit source manifest

Формат:
`{"schema_version":1,"sources":[{"path":"README.md","kind":"markdown"}]}`.
JSON/YAML description использует kind=schema. Paths относительные, без private
files, databases, reports и symlinks. YAML не исполняется. --manifest и
--state-dir указываются до command. Ошибка oversized source/chunk явная.

Реальный bge/Mac model-session прогон v0.2.2 выполнен; baseline comparison
сохранён в reports/verified/retrieval-mac-v022-baseline.json. Linux unit vectors
и witnesses синтетические. Фильтр заголовков v0.2.3 проверяется отдельно
без пересборки индекса: [команды](RETRIEVAL_FILTER.ru.md).
Официальный embed API: https://docs.ollama.com/api/embed .
