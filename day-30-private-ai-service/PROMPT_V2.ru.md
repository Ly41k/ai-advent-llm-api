# Этап 8 — установка проверенного prompt v2

## Основание и границы

Оригинальный Mac JSON: `reports/verified/prompt-compare-20261010-211034.json`,
SHA-256 `2981e322548805bcd894105cd548caa6be705f42563ad37e436e94800f5ea788`.
135/135 technical checks; 64/64 completed, 149.418 s, порядок A→B→B→A:

| Prompt | Контрольные ответы | long_a, два повторения |
|---|---:|---|
| private-chat-v1 | 24/26 | lantern, lantern — неверно |
| candidate-latest-request-v1 | 26/26 | OK, OK — верно |

История/последний запрос каждого случая побайтово совпадают во всех блоках.
Qwen digest/template, Ollama0.40.2 и OS engine epoch неизменны.
Temperature=0, max_output=1024, num_ctx=8192, margin=512 одинаковы.
Также прочитаны ответы про запоминание, исправление факта, смену темы,
русские приветствия и queue-контроли: новых ошибок не найдено.
Оригинальное semantic_review=pending_human_review не изменено; этот документ
фиксирует последующую проверку. Эксперимент использует замороженную историю,
stream:false и последовательный inference; он не доказывает работу нового API,
динамического чата, concurrency, first-token latency или RAM/CPU/GPU.
Ускорение не заявляем: медианы client total около 0.643 s почти одинаковы.

Кандидат принят **побайтово** под серверной версией `private-chat-v2`.
Он добавляет приоритет последнего запроса и его формата. Контекстная верхняя
граница long_a увеличилась на 40 байт, 6613→6653 при бюджете6656.
Это результат конкретных входов, не гарантия качества любого чата.

## Сохранность

Runtime **0.8.0**, schema **2**, API **v1**. Миграции БД и новых dependencies нет.
Immutable registry хранит оба текста; ContextBuilder/repository выбирают текст
по одной версии. Ollama проверяет соответствие текста snapshot версии до POST.
Новые генерации используют v2; старые owner/chat/message/generation IDs,
ответы и context/profile snapshots не переписываются. Повтор прежнего
idempotency key возвращает прежнюю генерацию v1 без inference.
Новая генерация в старом чате использует v2 и прежние completed пары в бюджете;
полная история остаётся в SQLite независимо от окна модели.

При queued заданиях другого профиля startup возвращает
`queued_profile_mismatch` до claim и сохраняет задания. Для временного возврата
есть `serve --prompt-version private-chat-v1`: также передайте прежние DB,
port, origins и trusted proxy. Сначала завершите старую очередь с v1, затем
переходите на v2. Не запускайте второй API и не удаляйте queued задания.
Running после незавершённого процесса требует прежней проверки recovery;
не запускайте recover лишь из-за смены prompt.

## 1. Остановить API перед заменой файлов

В терминале Mac:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
source ../.venv/bin/activate
python -m bublik_service \
  --db /Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3 storage-status
```

Продолжайте при queued=0, running=0, inference_recovery_required=false;
во время обновления не отправляйте вопросы с других устройств.
Если API ещё работает:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
```

Если он уже остановлен после эксперимента, bootout пропустите.
Ollama, Caddy и Tailscale оставьте работающими. Compare outcome_unknown=false,
перезапуск Ollama для этого обновления не нужен.
Распакуйте **day30-stage8-prompt-v2.zip** в корень
`/Users/litdi/AI/ai-advent-llm-api` с заменой файлов дня30.
Рабочей базы/секретов в архиве нет. Существующие launchd plists/root venv подходят.

## 2. Проверка и запуск

Из каталога дня30:

```bash
python scripts/verify_report.py reports/verified/stage8-prompt-v2-offline.json
python - <<'PY'
from bublik_service import __version__
from bublik_service.domain import ModelProfile
print({"version": __version__, "profile": ModelProfile().to_dict()})
PY
```

Ожидаются report_matches_sources_and_passed=true, version=0.8.0,
prompt_version=private-chat-v2. Hash check — не live model/network proof.

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
launchctl print "gui/$(id -u)/local.bublik.private-ai.api"
curl --max-time 10 \
  https://yuriys-macbook-pro.tail893c10.ts.net/api/v1/health/live
```

Ожидаются running и {"status":"alive"}; дождитесь «модель готова» в Web UI.
Bare HTTP127.0.0.1:8000 в trusted proxy режиме остаётся недопустимым.

## 3. Проверка старых чатов

Все следующие команды в одном терминале. Новый уникальный каталог:

```bash
BUBLIK_V2_DIR="$(mktemp -d "$HOME/bublik-day30-prompt-v2.XXXXXX")"
printf '%s\n' "$BUBLIK_V2_DIR"
python scripts/check_prompt_upgrade.py \
  --network tailnet \
  --url https://yuriys-macbook-pro.tail893c10.ts.net \
  --token-file /Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json \
  --baseline reports/verified/acceptance-baseline-20261010-202012.json \
  --output "$BUBLIK_V2_DIR/upgrade.json"
```

Read-only checker сверяет все 7 прежних чатов по полным history hashes и
16 прежних генераций по ответам/status/metrics/exposed context/времени/profilev1.
Ready должен показывать v2 и прежнюю identity модели. Изменение sources
здесь ожидаемо для явно выбранного перехода v1→v2; обычный `--history-from`
по-прежнему требует одинаковые sources. При failed передайте JSON и остановитесь;
reference/рабочую базу не исправляйте для прохождения проверки.

## 4. Новый API baseline

После passed в upgrade.json, без вопросов с других устройств во время проверки:

```bash
python scripts/check_acceptance_live.py \
  --network tailnet \
  --url https://yuriys-macbook-pro.tail893c10.ts.net \
  --token-file /Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json \
  --output "$BUBLIK_V2_DIR/baseline-v2.json"
```

Создаёт синтетические чаты: 10 последовательных вопросов с реальной
динамической историей, 3 русских приветствия, 3 конкурентных HTTP admission
при одной активной генерации, context/body overflow, 401, idempotency,
HTTP rate limit и OS sampling RAM/CPU/swap. Ожидаются technical_status=passed,
quality_status=passed (13/13), status=passed. Передайте JSON также при failed.
Не повторяйте старый frozen compare: он требует исходный v1 runtime.
Фактическая приёмка завершена: upgrade30/30, baseline259/259 technical и13/13
quality, history после API restart11/11, LAN/launchd6/6 с новымPID. Original passed
и failed отчёты сохранены раздельно; см. FINAL_REPORT.ru.md. Эти команды — процедура
повторной проверки, повторять upgrade без причины не нужно. Этап9 оформлен;
backup/перенос console-owner остаётся отдельным отложенным пунктом.
