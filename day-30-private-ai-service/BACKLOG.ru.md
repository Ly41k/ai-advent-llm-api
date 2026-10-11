# Bublik — отложенные задачи и развитие после дня30

Базовый runtime0.8.0 принят в проверенной конфигурации; расширение0.9.1
добавляет FTS5 RAG обеих сторон переписки, включённый по умолчанию в Web UI; его live-приёмка выполняется отдельно. Базовая история/owners,
API/UI, queue/quotas и versioned prompt реализованы. Ниже — отдельные задачи,
за пределами принятого задания дня 30. См. FINAL_REPORT.ru.md.

Контракт сохранности: [MEMORY_ARCHITECTURE.ru.md](MEMORY_ARCHITECTURE.ru.md).
Следующий этап — научить модель искать/применять память: semantic retrieval,
разрешение отсылок, многошаговое чтение источников, датированные противоречия,
версионируемые summaries/facts с provenance. Их данные должны входить в archive;
оригиналы не заменяются и не удаляются автоматически.

## После курса

- Python → Rust / Axum / Tokio: отдельное сопоставимое исследование API overhead.
  Сейчас Rust не внедряется. Одинаковые API, данные, модель, оборудование и нагрузка;
  измерять RAM, CPU, latency, concurrency, stability. API-память отдельно от Qwen
  и KV-cache; экономия памяти модели от переписывания API не заявляется.
- Exact local tokenizer, если проверены vocabulary/template/digest и ресурсы.
- Улучшение доступа к старой истории без её потери: summary с provenance и
  независимым оригиналом. FTS5 retrieval обеих сторон переписки и original-context API
  реализованы в0.9.1; embeddings/перефразировки, версионируемые факты, corrections
  и систематическая проверка противоречий остаются отдельными этапами.
- Off-host/encrypted backups, расписание и retention; RAID/mirror не заменяет backup.
- Branching, редактирование/удаление/экспортные политики, revoke-all/session management.
- Масштабирование процесса worker/queue, больше parallel inference только после замеров.
- Голос, MCP/tools и автономные действия — отдельные будущие решения.

## После полной реализации дня 30

- Первый инструмент [verified archive/restore](MEMORY_PORTABILITY.ru.md) добавлен
  после дня 30. Приёмка архива и отдельной восстановленной копии личной базы
  выполнена оператором на том же Mac; физический новый хост ещё не проверен.
  Расписание, шифрование/off-host копии, retention, аварийный restore pending
  inference и перенос полезной истории старого console owner остаются отдельно.
  Базовый SQLite backup API сохраняется.
- UI: безопасный локальный Markdown renderer/code blocks, user-controlled export,
  темы/доступность и расширенная работа с очень большими списками диалогов.
  Не добавлять CDN, сырые HTML ответы или persistent browser copies личной истории.

- UI-видео записано пользователем: чат и сообщения с телефонов.
  CONSOLE_VIDEO.ru.md остаётся необязательным сценарием повторной демонстрации.
- При необходимости вернуться к прямому LAN с телефона без Tailscale: trust
  собственного CA, phone Wi-Fi-only условия и отдельный свежий handoff report.
  Основной Tailscale URL не требует этих сертификатов.
- Независимо проверить сохранённую tailnet policy (grants и legacy ACLs), policy
  tests и fresh Serve/Funnel status; narrow grant не отменяет broad allow.
- Independent physical remote probes к8000/11434 в LAN/tailnet и security review;
  Mac self-probes не заменяют внешний scanner.


## Ограничения и дальнейшая проверка

- Исторический long_a failure исправлен и принят для текущего набора: frozen
  ABBA candidate26/26 противv1 24/26, новый dynamic API baseline13/13. Не удалять
  failed original. Дальнейшие quality tests расширять на новые независимые
  multi-turn inputs/RU/EN, не выдавать13controls за универсальное качество.
- Paged/streaming export для очень больших чатов: текущий согласованный snapshot
  материализуется в памяти; измерить цену и сохранить формат/consistent semantics.

- Ограниченная структурированная диагностика для launchd вместо /dev/null,
  с редактированием секретов, без content logging, с rotation/retention.
- Отдельный always-on host/LaunchDaemon deployment при необходимости доступа
  до user login; не обходить FileVault или sleep незаметно.

- Более точные physical-footprint/GPU/pressure measurements на Apple Silicon,
  Instruments и продолжительный soak test. Sampled RSS/ps CPU и Ollama allocations
  этапа 8 не заменяют physical unified-memory accounting или GPU utilization.
- Отдельный benchmark identity diff: model weights/template/profile и engine
  version показывать раздельно, требовать явного анализа изменений. Не переписывать
  strict stage7 reports после изменения Ollama 0.34.4 → 0.40.2.
