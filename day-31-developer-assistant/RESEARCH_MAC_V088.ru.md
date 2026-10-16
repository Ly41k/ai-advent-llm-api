# Mac — v088 / 0.7.18

Из корня ai-advent-llm-api, в активном установленном .venv. Day30/другие Ollama
clients отключены; выделенная confirmed session прежняя. Не перезапускать
Ollama ради обычного обновления prompt; при real epoch change соблюдать gate.

```bash
unzip -o ~/Downloads/day31-stage7-v088.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v088_mac.sh
```

Ожидаем 0.7.18. Unzip объединяет файлы только Day31; не заменять scripts через
Finder. Все 59 Python / десять критических scripts включены; dependencies прежние.

Helper проверяет новые output names до model operations, full native 259 tests,
existing CURRENT, bilingual source/admission checks, GET /api/version и совпадение
59 SHA. Preflight использует separate temporary FTS smoke index и реальные
Git/owned workers, generation0/embedding0. CURRENT он не заменяет.
Затем original known unsupported-knobs-ru: один production Documentation call,
FTS, cap1, zero embeddings, fresh version/prompt/schema/model/index freeze.
Нет auto next packet. Правильный control: unknown и claims=[], не unsupported
identifier/refusal claim. Один успех не закрывает overall semantic quality.

Прикрепить семь новых files:

```text
/tmp/day31-stage7-preflight-mac-v088.json
/tmp/day31-index-verify-mac-v088.json
/tmp/day31-quality-admission-mac-v088.json
/tmp/day31-ollama-version-mac-v088.json
/tmp/day31-diagnostics-plan-mac-v088.json
/tmp/day31-diagnostics-freeze-mac-v088.json
/tmp/day31-diagnostics-unknown-ru-mac-v088.json
```

Не удалять и не повторять completed outputs. Helpers stops при existing files,
source mismatch или bad plan до generation. Failed/interim reports сохраняются.
Не использовать старый freeze для новой версии; index build не нужен.

После review первого control доступны отдельные commands:

```bash
bash day-31-developer-assistant/scripts/continue_v088_mac.sh unknown
bash day-31-developer-assistant/scripts/continue_regression_v088_mac.sh main
```

Unknown: 4 answers / cap4. Main: 4 answers / cap6. Не запускать их автоматически
подряд. Native suite после matching 259 preflight не повторяется; SHA guard59
перед каждым packet обязателен. Каждый packet использует new paired snapshot
freeze и пишет /tmp/day31-paired-<packet>-mac-v088-{index-verify,plan,freeze,result}.json.
Остальные available packets: continue_v088 serialized6/untracked4;
continue_regression_v088 receipt4/assistant4/dense6/language4/paths6/paraphrase4/
uncertain6. Model calls сериализованы shared lease. /api/ps не является отдельным
completion witness; automatic model retry/cloud fallback/restart отсутствуют.

Этап 7 открыт; 8 только после уведомления о закрытии и согласования с Юрием.
[Изменение и результаты v087](CHANGES_V088.ru.md).
