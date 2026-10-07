# V12 — OpenAI API внутри Day 28

Живой результат теперь получен: [OPENAI_RESULTS.ru.md](OPENAI_RESULTS.ru.md). Ниже сохранена исходная инструкция и состояние offline-проверки перед запуском. Повторять команду для текущего задания не требуется.

Добавлен отдельный OpenAIProvider в cloud28.py. Groq остаётся по умолчанию; OpenAI выбирается явно через --cloud-provider openai. Ключ OPENAI_API_KEY берётся из окружения или существующего корневого .env. GROQ_API_KEY не используется как fallback. SDK OpenAI не требуется: вызовы выполняются через общий HTTP-транспорт. Другие дни, корень и индекс не меняются; переиндексация не нужна.

## Подключение и протокол

- Endpoint закреплён: https://api.openai.com/v1 .
- По умолчанию для OpenAI закреплена версия gpt-4.1-mini-2025-04-14. Алиас gpt-4.1-mini разрешается в неё до сохранения настроек/запросов. Также поддержаны gpt-4o-mini и snapshot gpt-4o-mini-2024-07-18. Остальные модели не включены: их параметры/форматы требуют отдельной проверки.
- Preflight /models проверяет доступ проекта к snapshot; доступность модели не гарантирует достаточный баланс или отсутствие rate limits.
- Chat Completions использует max_completion_tokens, temperature=0, store=false; gpt-oss reasoning_effort в OpenAI не отправляется.
- Для обоих supported snapshots отправляется native response_format=json_schema, strict=true. Объекты закрыты, все поля обязательны; nullable слоты и enum точных ID приходят из retrieved источников. Обычный режим — evidence_claims_v8; --synthesis — два этапа с вторым quote_slots_v4. Приложение продолжает проверять IDs, цитаты, полноту и rubric.
- Ответ другой snapshot, пустой/неполный output, неправильная форма ответа/usage или provider refusal не становятся успешным RAG ответом. 401 указывает на OPENAI_API_KEY. Тексты секретов и Authorization не включаются в отчёт.
- Отчёты schema_version=12 содержат cloud_api на уровне прогона, preflight и cloud наблюдений; settings.cloud_provider и pinned cloud_model. В роли провайдера остаётся cloud для совместимости метрик. Независимый verifier сверяет API, endpoint, snapshot и generated model. Старые V2–V11 проверяются как прежде.
- --retry-from запрещает перенос результатов между cloud API/моделями. OpenAI запускается в новом отчёте без Groq baseline. Сохранённые результаты не переименовываются и не переписываются.

## Первый небольшой запуск

questions-openai-small.json содержит исходные вопросы и неизменённые рубрики для base-03 (preflight/postflight), base-10 (VPS) и rewrite-ru-02 (SQLite/изоляция диалогов). Три разных темы выбираются заранее, включая известную проблему качества облака. Это не все 20 вопросов и не новая полная оценка.

```bash
python day-28-local-rag/main.py compare   --cloud-provider openai --only-provider cloud   --questions day-28-local-rag/questions-openai-small.json   --repeats 3 --max-tokens 1000 --cloud-rate-retries 0   --output day-28-local-rag/reports/check/openai-small-v12.json

python day-28-local-rag/verify_report.py   day-28-local-rag/reports/check/openai-small-v12.json
```

Максимум 9 логических генераций и 9 HTTP generation попыток. Synthesis выключен; max output 1000 tokens на пробу. Rate retries выключены явно: при 429 cloud остановится, оставшиеся наблюдения будут записаны как пропущенные/error. Невалидные/некачественные ответы не исправляются повторной генерацией. Local Qwen не вызывается; локальные bge-m3 embeddings и SQLite retrieval всё ещё нужны. Запустите Ollama с установленным bge-m3 и используйте существующий knowledge.db.

Не нужно --retry-from compare-v2: другая модель и другой API требуют отдельного отчёта. Предыдущие local/Groq результаты остаются историей. Cloud-only отчёт помечается как отдельное измерение без нового парного local/cloud сравнения. Вопросы общие с прежним набором, но версии prompts/режимы различались: старые local времена и новый cloud subset нельзя выдавать за общий свежий benchmark. Если позже понадобится строго парная новая оценка, она потребует отдельного запуска выбранного маленького набора у обеих моделей и согласованного режима; сейчас локальные вопросы повторно не запускаются.

## Бюджет и проверка

Цены gpt-4.1-mini проверены по официальной странице 2026-10-07: $0.40 за миллион входных и $1.60 за миллион выходных токенов. Источник: https://developers.openai.com/api/docs/models/gpt-4.1-mini . При условных 6000 input +500 output на запрос девять запросов стоят $0.0288, без скидки кеша. При 1000 output и том же входе — $0.036. Это расчётный пример, не жёсткий cap и не измеренный расход; длина источников/токенизация различаются. Баланс API и rate limits учитываются отдельно.

63 offline-теста Day 28 прошли (57 прежних и 6 новых): API routing без local generation/Groq, key selection, strict schemas обоих этапов, pinned model/usage/refusal/completion, provenance tampering, missing key, cross-provider retry, исходные small рубрики. Выполнены compileall, git diff --check, совместимость verifier с 12 историческими JSON. Детали: reports/verified/v12-validation.json. Тесты не выполняли платных API вызовов и не обращались к пользовательскому ключу. Live OpenAI пока pending; нужен openai-small-v12.json с вашего Mac.

Для самостоятельной offline-проверки:

```bash
python -m unittest discover -s day-28-local-rag -p 'test*28.py'
```

Итог Дня 28 до этого дополнительного эксперимента сохранён в FINAL_REPORT.ru.md. V12 не меняет результаты V11 и не объявляет качество OpenAI проверенным до получения живого отчёта.
