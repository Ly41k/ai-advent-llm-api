# Исправление engine_process_unverified на Mac — 2026-10-10

## Подтверждённая причина

На Mac пользователя Ollama 0.34.4 слушала 127.0.0.1:11434 под тем же UID 501.
Проверки listener, UID и start time проходили. Команда
`ps -axo pid=,ppid=,comm=` завершилась с return_code=0 за 0.042 s, но вернула
66 366 символов / 688 строк. Общий лимит нашего `_command` составлял 65 536
символов. Поэтому здоровый процесс ошибочно получал `engine_process_unverified`,
а UI показывал «Модель временно недоступна · история доступна».

База schema=2: integrity=ok, foreign_key_violations=0, queued=running=0,
inference_recovery_required=false. Это ручные наблюдения пользователя в чате,
не подписанный отчёт и не успешная генерация через телефон.

## Изменение

Только для точной команды списка процессов допустимый размер увеличен до
1 048 576 символов. Остальные команды сохраняют лимит 65 536 и timeout=3 s.
Список проверяется полностью: обрезка или игнорирование ошибки запрещены, иначе
можно пропустить orphan runner. Не изменены localhost isolation, UID/start time,
process ancestry/orphan checks, модельный профиль, схема БД, owner IDs и recovery.
Версия остаётся 0.5.0; точную ревизию определяют source hashes.

## Установка небольшого исправления

Дождитесь окончания активных генераций. Остановите только API через Ctrl+C в
его терминале. Caddy и Ollama оставьте запущенными.

Распакуйте `day30-stage6-engine-fix.zip` поверх каталога репозитория с заменой
файлов. Архив содержит префикс `day-30-private-ai-service/`: распаковывайте в
`/Users/litdi/AI/ai-advent-llm-api/`, а не внутрь каталога дня.
В архиве нет БД, токенов, сертификатов и приватных ключей.

Из каталога дня с активной .venv:

```bash
python scripts/verify_report.py reports/verified/stage6-engine-fix-offline.json
python -m bublik_service \
  --db "/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3" doctor
```

Hash verifier должен вернуть true при полном совпадении установленного этапа 6.
Doctor должен вернуть сведения о модели. Если сохраняется ошибка, пришлите её;
не меняйте service_state и не запускайте recover-inference без recovery gate.

Запустите API заново в прежнем терминале:

```bash
python -m bublik_service \
  --db "/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3" \
  serve --port 8000 --trusted-loopback-proxy \
  --origin "https://192.168.0.247:8443"
```

Адрес здесь соответствует текущему IP Mac; при его смене нужны согласованные
origin и Caddy configuration. Обновите страницу на Mac/телефоне, убедитесь, что
модель готова, и отправьте контрольный вопрос. Новые network/handoff reports
создавайте с новыми именами: runtime hash изменился.

## Проверки и границы

Добавлены три regression tests: таблица больше 64 KiB проходит; orphan runner
после границы 64 KiB по-прежнему блокирует engine; вывод сверх нового лимита,
ошибка команды, timeout и старый лимит остальных команд по-прежнему отвергаются.
Они выполняют реальный parser с подменой subprocess results, не доказывают
Ollama/Qwen на Mac. Полный новый offline report сохраняется отдельно как
`reports/verified/stage6-engine-fix-offline.json`. Прежние отчёты не переписаны;
их source hashes относятся к предыдущей ревизии. Реальные Mac doctor / phone
chat после исправления требуют повторной проверки.
