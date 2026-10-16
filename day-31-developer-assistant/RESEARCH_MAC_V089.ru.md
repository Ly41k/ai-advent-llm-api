# Mac — v089 / 0.7.19

Из корня ai-advent-llm-api, активный установленный .venv. Dependencies прежние.
Day30 и другие Ollama clients отключены; confirmed dedicated session остаётся.

```bash
unzip -o ~/Downloads/day31-stage7-v089.zip -d .
python day-31-developer-assistant/main.py --version
bash day-31-developer-assistant/scripts/run_v089_mac.sh
```

Ожидаем 0.7.19. Unzip объединяет файлы только Day31; не заменять scripts через
Finder. Все59 Python и10критических scripts включены. Другие дни/root README
не включены в архив. Existing CURRENT44/405 не перестраивать.

Первый helper проверяет output names до model ops, full native259, CURRENT,
bilingual source/admission, GET /api/version и59SHA. Offline smoke строит
отдельный temporary FTS index, generation0/embedding0, реальные Git/workers;
CURRENT не заменяет. Затем fresh production freeze и один positive RU Doc
control main-doc-ru, max-generation-calls1, FTS, zero embeddings. Exact scoped
question соответствует предыдущему Main RU input; реального Git вопроса и
Main assembly в этом control нет. Нет auto continuation или retry.

Прикрепить семь новых reports:

```text
/tmp/day31-stage7-preflight-mac-v089.json
/tmp/day31-index-verify-mac-v089.json
/tmp/day31-quality-admission-mac-v089.json
/tmp/day31-ollama-version-mac-v089.json
/tmp/day31-diagnostics-plan-mac-v089.json
/tmp/day31-diagnostics-freeze-mac-v089.json
/tmp/day31-diagnostics-main-ru-mac-v089.json
```

Проверяется justified answered при доступной поддержке, exact Main spelling,
claim citations и полнота. Schema-valid partial не будет повышен приложением.
Один control не закрывает semantic acceptance или полный Main packet.
Existing reports не удалять; тот же helper не replay. Старые freezes не
использовать для новой версии. Обновление prompt не требует restart Ollama;
при реальном epoch change соблюдать gate/recovery, не обходить проверки.

После review доступны отдельные commands:

```bash
bash day-31-developer-assistant/scripts/continue_v089_mac.sh unknown
bash day-31-developer-assistant/scripts/continue_regression_v089_mac.sh main
```

Unknown4answers/cap4; Main4answers/cap6. Не запускать автоматически подряд.
Matching native259 используется повторно, но source guard59 обязателен.
Каждый packet: fresh paired freeze; четыре reports по prefix
/tmp/day31-paired-<packet>-mac-v089-{index-verify,plan,freeze,result}.json.
Остальные available: continue_v089 serialized6/untracked4;
continue_regression_v089 receipt4/assistant4/dense6/language4/paths6/paraphrase4/
uncertain6. Calls последовательно shared lease; no embeddings/rebuild/replay.

Этап7 открыт;8только после закрытия7и согласования. [Изменения](CHANGES_V089.ru.md).
