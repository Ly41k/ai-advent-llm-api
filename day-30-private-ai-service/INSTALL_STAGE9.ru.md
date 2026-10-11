# Установить итоговую документацию этапа9

Для текущей установки0.8.0/private-chat-v2. Архив `day30-stage9-final.zip` содержит
root README и полный каталог дня30; рабочая DB/токены/TLS/venv в него не входят.
Ниже устанавливаются **только документы и отсутствующие evidence JSON**. Runtime,
launchd/Caddy configs и личная история не изменяются; API не надо останавливать.
Для новой установки используйте README/RUNBOOK вместо этого раздела.

В активном root venv из каталога дня30:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
source ../.venv/bin/activate
BUBLIK_STAGE9_UNPACK="$(mktemp -d "$HOME/bublik-day30-final.XXXXXX")"
unzip "$HOME/Downloads/day30-stage9-final.zip" -d "$BUBLIK_STAGE9_UNPACK"
python scripts/verify_report.py \
  "$BUBLIK_STAGE9_UNPACK/day-30-private-ai-service/reports/verified/stage8-prompt-v2-offline.json"
```

Ожидается report_matches_sources_and_passed=true: ваши runtime/tests/scripts/configs
совпадают с архивом. Если false, остановитесь и выясните отличие; это не повод
перезаписать рабочий код. После true в том же терминале:

```bash
python - "$BUBLIK_STAGE9_UNPACK" <<'PY'
import json
import shutil
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from check_storage import manifest
bundle = Path(sys.argv[1])
source = bundle / "day-30-private-ai-service"
target = Path.cwd()
assert (target / "bublik_service/__main__.py").is_file(), "Run from Day30"
baseline = json.loads((source / "reports/verified/stage8-prompt-v2-offline.json").read_text())
assert manifest() == baseline["source"]["source_sha256"], "Source mismatch; nothing copied"
reports = list((source / "reports/verified").glob("*.json"))
for item in reports:
    destination = target / "reports/verified" / item.name
    if destination.exists() and destination.read_bytes() != item.read_bytes():
        raise SystemExit("Conflicting existing report; nothing copied: " + item.name)
for name in ("README.md", "README.ru.md"):
    shutil.copy2(bundle / name, target.parent / name)
docs = list(source.glob("*.md"))
for item in docs:
    shutil.copy2(item, target / item.name)
(target / "reports/verified").mkdir(parents=True, exist_ok=True)
added = 0
for item in reports:
    destination = target / "reports/verified" / item.name
    if not destination.exists():
        with destination.open("xb") as stream:
            stream.write(item.read_bytes())
        added += 1
print(json.dumps({"docs_copied": len(docs) + 2, "new_reports_added": added,
                  "existing_reports_overwritten": 0, "runtime_changed": False}))
PY
```

Скрипт сперва проверяет все existing report conflicts и source manifest. Он не
переписывает ни один historical JSON, не копирует `.py`/SQL/config и не открывает
DB. Для ревью Git из корня: `git --no-pager diff --stat`, затем
`git --no-pager diff -- README.md README.ru.md day-30-private-ai-service`.
Коммит/публикация отдельно; API/чат продолжают работать.

Root README меняет Day21 corpus. Перед будущим strict RAG run нужен отдельный
build/verify индекса; не запускайте bge-m3 во время Qwen приёмки. Для чата дня30
rebuild не требуется. Operational backup/restore остаётся следующим согласуемым пунктом.
