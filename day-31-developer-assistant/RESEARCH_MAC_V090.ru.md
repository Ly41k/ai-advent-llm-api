# Mac — v090 / 0.7.20

Из корня ai-advent-llm-api, активное прежнее окружение .venv. Dependencies прежние.
Day30 и другие Ollama clients отключены. Dedicated session confirmed.

```bash
unzip -o ~/Downloads/day31-stage7-v090.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v090_mac.sh
```

Версия 0.7.20. Unzip объединяет файлы; не заменять scripts через Finder.
Архив включает только Day31, все59 Python и10 critical scripts.
CURRENT44/405 не перестраивать. Prompt update не требует restart Ollama;
при фактическом epoch change соблюдать gate/recovery.

Helper проверяет новые output names до model operations, full259 tests,
CURRENT, admission6, GET /api/version,59 SHA и original catalog. Preflight
строит отдельный temporary FTS smoke index с реальными Git/workers, generation0
и embedding0; CURRENT не заменяет. Затем fresh production freeze и только
один RU Documentation unknown control unsupported-knobs-ru, cap1, FTS, zero
embeddings. Нет automatic continuation/retry. Полнота positive ответов pending.

Прикрепить семь новых reports:

```text
/tmp/day31-stage7-preflight-mac-v090.json
/tmp/day31-index-verify-mac-v090.json
/tmp/day31-quality-admission-mac-v090.json
/tmp/day31-ollama-version-mac-v090.json
/tmp/day31-diagnostics-plan-mac-v090.json
/tmp/day31-diagnostics-freeze-mac-v090.json
/tmp/day31-diagnostics-unknown-ru-mac-v090.json
```

Старые reports/freezes не удалять/не использовать для новой версии. Если
helper stopped, сохранять JSON и не повторять команду с теми же именами.
Completed terminal reply, rejected приложением, остаётся known call; сам по
себе отказ format validation не требует recovery/restart.

После review доступны отдельные commands:

```bash
bash day-31-developer-assistant/scripts/continue_v090_mac.sh unknown
bash day-31-developer-assistant/scripts/continue_v090_mac.sh serialized
bash day-31-developer-assistant/scripts/continue_regression_v090_mac.sh main
```

Не запускать автоматически подряд. Unknown cap4; serialized/Main cap6, по
2questions/4observations, один paired repeat. Matching native259 используется
повторно с обязательным source guard. Каждый packet создаёт fresh freeze и
четыре /tmp/day31-paired-<packet>-mac-v090-{index-verify,plan,freeze,result}.json.
Остальные helpers доступны как прежде. Ни один packet не rebuild CURRENT и не
делает embedding calls. [Изменения и ограничение acceptance](CHANGES_V090.ru.md).
Этап7 открыт;8только после закрытия7 и согласования с Юрием.
