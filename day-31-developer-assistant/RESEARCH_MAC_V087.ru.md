# Mac: v087 / 0.7.17

Выполнять из корня ai-advent-llm-api в активном установленном .venv.
Day30 и другие Ollama clients выключены; выделенная confirmed session остаётся.
Failed completed reply v086 сам по себе не требует restart/recovery. При
реальном изменении epoch следовать явному status/gate, не обходить его.

```bash
unzip -o ~/Downloads/day31-stage7-v087.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v087_mac.sh
```

Ожидаем 0.7.17. Unzip объединяет файлы Day31; не заменять папку scripts через
Finder. Другие дни и root README архив не содержит. Dependencies прежние.

Первый helper проверит новые имена output files до model operations, полный
native 259-test preflight, existing CURRENT, bilingual admission, GET /api/version
и 59 Python digests. Preflight создаёт только отдельный temporary FTS smoke index;
generation0/embedding0, CURRENT не заменяет. Диагностический plan: original known
unsupported-knobs-ru, один production Documentation request, cap1, FTS mode,
zero embeddings. Новый freeze pinning версии/prompt/schema/index/model. Никакого
auto next packet. README/reports/tests/prompts не требуют index build.

Прикрепить семь новых файлов:

```text
/tmp/day31-stage7-preflight-mac-v087.json
/tmp/day31-index-verify-mac-v087.json
/tmp/day31-quality-admission-mac-v087.json
/tmp/day31-ollama-version-mac-v087.json
/tmp/day31-diagnostics-plan-mac-v087.json
/tmp/day31-diagnostics-freeze-mac-v087.json
/tmp/day31-diagnostics-unknown-ru-mac-v087.json
```

Правильный negative ответ — unknown и claims=[]; общие цитаты не доказывают
названный механизм/его параметры. One success не закрывает semantic quality.
Не запускать повторно тот же helper, не удалять existing reports ради replay.
Ниже команды отдельных последующих packets, только после review первого отчёта:

```bash
bash day-31-developer-assistant/scripts/continue_v087_mac.sh unknown
bash day-31-developer-assistant/scripts/continue_regression_v087_mac.sh main
```

Unknown: 2 questions / 4 observations / cap4; Main: 2 questions / 4 observations /
cap6, сравнение на общем snapshot, не E2E. Новые paired freezes; suite259 не
повторяется после matching preflight, но source guard59 обязателен. Для каждого
packet четыре новых /tmp/day31-paired-<packet>-mac-v087-{index-verify,plan,freeze,result}.json.
Не запускать обе команды автоматически подряд. Остальные доступные packets:
continue_v087: serialized(cap6),untracked(cap4); continue_regression_v087:
receipt4,assistant4,dense6,language4,paths6,paraphrase4,uncertain6. Обработка модельных
вызовов последовательная через shared lease; no model retries/cloud fallback.

Этап 7 открыт; начало этапа 8 согласовать после закрытия 7. [Изменения](CHANGES_V087.ru.md).
