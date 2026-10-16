# v086 / 0.7.16 — первый контроль, максимум один Doc call

Из корня repo, в активном текущем Python 3.13 окружении:

```bash
unzip -o ~/Downloads/day31-stage7-v086.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v086_mac.sh
```

Ожидается 0.7.16. unzip объединяет содержимое каталогов: не заменять scripts целиком
через Finder. Полный ZIP содержит все 59 Python, включая 10 проверочных scripts.
Dependencies прежние. Существующий hybrid CURRENT 44 docs/405 chunks используется.

Helper проверяет отсутствие семи output files до model operations. Затем:
259 native tests и реальный временный FTS/Git/worker smoke без генерации,
verify CURRENT, zero-model bilingual admission, GET /api/version,
source59/catalog guards, diagnostic plan и новый production freeze.
Temporary FTS smoke не заменяет CURRENT; bge-m3 embeddings не вызываются.

Первый запрос — EXACT routed Documentation question от main-authority-branch-ru,
где v085 остановился. В отдельном diagnostic catalog снята только Git-часть,
потому что сейчас проверяется один Doc output. Вопрос/источники остаются real
retrieval inputs. Original22 known catalog и его rubric НЕ изменены.

Один production Documentation request, максимум 1 Qwen call. Main assembly,
Single/Multi comparison и текущая ветка здесь не проверяются. Case labels/rubric
не входят в модельный контекст. Новый freeze pin содержит отдельный diagnostic
catalog SHA. Это не новая independent/held-out question и не полный Main pair.

Day30 и другие Ollama clients выключены для выделенной сессии. Существующие v085
reports сохранить; main v085 не повторять. При stopped outputs не удалять,
helper не повторять. Автоматического restart/retry/cloud fallback нет. При закрытом
gate действует прежняя операторская verified recovery процедура; completed-output
validation rejection сам по себе не требует перезапуска.

После возвращения prompt терминала прислать вывод и семь файлов:

```text
/tmp/day31-stage7-preflight-mac-v086.json
/tmp/day31-index-verify-mac-v086.json
/tmp/day31-quality-admission-mac-v086.json
/tmp/day31-ollama-version-mac-v086.json
/tmp/day31-diagnostics-plan-mac-v086.json
/tmp/day31-diagnostics-freeze-mac-v086.json
/tmp/day31-diagnostics-main-ru-mac-v086.json
```

После review доступны paired continue_v086_mac.sh unknown/serialized/untracked и
continue_regression_v086_mac.sh receipt/assistant/dense/language/paths/main/paraphrase/uncertain.
Каждый вызов — отдельный RU/EN packet cap4/6 и новый paired freeze без повторной
full suite. Сейчас запускать только run_v086_mac.sh; следующих packets нет автоматически.
Затем нужно проверить unknown и проблемные citation/coverage cases на новом prompt.

[Полная сводка, изменение и остаток этапа 7](CHANGES_V086.ru.md).
Этап 7 открыт; после завершения уведомить Юрия и согласовать начало 8.
