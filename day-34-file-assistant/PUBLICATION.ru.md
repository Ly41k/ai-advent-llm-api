# Публикация Day 34 — подготовлено, remote writes требуют отдельного разрешения

Проверенный base main: `25ba00685d0748ebe533570711b75e0d187ab20b`, PR #5 и #6 объединены. Локальная ветка поставки: `feat/day34-file-assistant`. В будущем PR входят только новая папка Day 34 и два корневых README. Дни 1–33 не меняются. Индексы не перестраиваются.

Предлагаемое название PR:

`feat(day34): file assistant with real tool selection and reviewed Course Minimum acceptance`

Описание PR:

> Adds a bounded file assistant that selects read/search/write operations through real LLM decisions for Usage and ticket-context ADR scenarios. Retains original Markdown, creation diffs, source evidence, saved-decision replay and separate editorial corrections. Technical acceptance and Usage pass; the original ADR remains PARTIAL, the independently reviewed ADR passes, and Course Minimum is accepted with that review. Historical NOT_ACCEPTED reports remain unchanged.
>
> Validation: Mac v7 65/65 offline; final delivery verifier checks source/output SHA, exact editorial diff, both zero-POST replays, public file scope and the existing 65 tests. No new cloud calls. Only Day 34 and root README RU/EN change; no earlier lesson or RAG index changes.

## На Mac после применения архива

Из корня своего репозитория:

```bash
git status --short
git rev-parse main
git switch -c feat/day34-file-assistant main
python3.13 day-34-file-assistant/verify_delivery.py
```

Если эта ветка уже существует, использовать `git switch feat/day34-file-assistant`, не сбрасывать её. Если main продвинулся, сначала проверить различия; архив рассчитан на указанный base. Не использовать reset/clean для удаления своих результатов.

Добавить **ровно** файлы manifest, сохраняя старые приватные results и receipts вне индекса:

```bash
python3.13 - <<'PY'
import json
from pathlib import Path
import subprocess
m = Path('day-34-file-assistant/delivery-manifest.json')
paths = sorted(json.loads(m.read_text())['files_sha256']) + [m.as_posix()]
subprocess.run(['git', 'add', '--', *paths], check=True)
PY
git status --short
git diff --cached --name-only
git diff --cached --stat
git diff --cached --check
python3.13 day-34-file-assistant/verify_delivery.py
```

Не выполнять `git add .`: локально остаются приватные материалы, старые попытки, caches и временные результаты. Verifier проверяет Git index и выдаёт FAIL для staged-файлов вне разрешённого состава. `.DS_Store`, `.venv`, `__pycache__`, `results/` не входят в публикацию. В публичных traces нет сырых HTTP-запросов, provider IDs и receipts. Шаблоны ключей и локальных абсолютных путей проверяются по публикуемым файлам; это минимальная проверка состава, не универсальный secret scanner.

## Только после отдельного разрешения на публикацию

Следующие команды **подготовлены, но не выполнялись**:

```bash
git commit -m "feat(day34): complete file assistant course minimum with editorial review"
git push -u origin feat/day34-file-assistant
```

После push создать PR через GitHub UI: base `main`, compare `feat/day34-file-assistant`, название и описание выше. Создание PR тоже требует отдельного разрешения. Проверить GitHub Files changed: только Day 34 и корневые README. Merge — отдельное действие по разрешению владельца.

Фактический diff/stat подготовленного локального индекса передаётся вместе с архивом. Новые модельные вызовы, Ollama и повторная приёмка через облако не нужны. Видео записывается по [CONSOLE_VIDEO.ru.md](CONSOLE_VIDEO.ru.md).
