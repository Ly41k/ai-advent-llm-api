# Recovery checker: исправление контрольного запроса

Две попытки не доказали прерывание. Вторая диагностика показала, что Qwen
вместо 500 предложений написала отказ из 80 токенов; после сигнала оставалось
около шести секунд. Это не потеря истории и не повод снимать recovery gate.
Текущий READY200/ready/no gate означает, что recover-inference не требуется.

Обновление меняет только два script/test файла и документы/отчёты. Default
system prompt, API, UI, профиль 8192/1024/0, schema2 и рабочая база не меняются.
Не требуется перезапуск API или переустановка runtime dependencies.

## Установка

Распакуйте `day30-stage8-recovery-fix.zip` в корень репозитория с заменой файлов
внутри `day-30-private-ai-service`. Личные DB/token/Tailscale/Caddy state в HOME
не входят в архив. Не удаляйте исходные JSON.

Старый baseline остаётся свидетельством того же runtime. Его полный manifest
теперь отличается ровно в scripts/check_recovery_live.py и tests/test_acceptance.py.
Не запускайте strict history-from старого baseline на новом checkout: он ожидает
тот же полный source. Baseline/history повторим после quality experiment;
long_a instruction failure этим обновлением не исправлен.

## Новый контроль

В каталоге дня 30, с активным root venv, API/Ollama/Tailscale ready и без других
генераций. Подготовьте меню Ollama → Quit, но пока не выходите.

```bash
BUBLIK_RECOVERY_DIR="$(mktemp -d "$HOME/bublik-day30-recovery.XXXXXX")"
printf '%s\n' "$BUBLIK_RECOVERY_DIR"

python scripts/check_recovery_live.py prepare \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_RECOVERY_DIR/prepare.json"
```

При `interrupt_Ollama_now` сразу Quit в Ollama. API/Caddy/Tailscale оставьте
работать. Если prepare failed или ответ успел закончиться, прерывание не доказано;
передайте новый JSON. Скрипт теперь сохраняет actual control status/text/metrics.

Подождите минимум 5 секунд после Quit. В той же консоли:

```bash
python scripts/check_recovery_live.py interrupted \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --baseline "$BUBLIK_RECOVERY_DIR/prepare.json" \
  --output "$BUBLIK_RECOVERY_DIR/interrupted.json"
```

Ожидается passed: failed/interrupted generation, сохранённый prefix/seed history,
live/history доступны, ready503/no model/gate, новый send503 без history insert.
Передайте два JSON; Ollama пока не открывайте снова. Этап restored выполняется
после разбора interrupted по STAGE8.ru.md. Никакого replay старой генерации.

Новый prompt forest-story-v2 хранится вместе с challenge. Реальная длительность
ещё не измерена; synthetic test не доказывает, что Qwen выдаст длинный рассказ.

Проверка реализации: 8/8 targeted tests, полный suite **136/136** (46.589 s),
ResourceWarning как ошибка, current source hashes=64. Реальная Qwen в этих
тестах не использовалась. Исходный Mac baseline и failed reports сохранены.
