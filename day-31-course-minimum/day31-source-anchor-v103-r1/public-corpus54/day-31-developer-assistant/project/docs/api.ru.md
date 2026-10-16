# API приватного сервиса дня 30

## Префикс API и проверка доступности

День 30 определяет PREFIX=/api/v1 в bublik_service/http_api.py.
GET /api/v1/health/live проверяет liveness, GET /api/v1/health/ready — readiness.
Одна liveness-проверка не подтверждает успешную генерацию Qwen.

## Диалоги, сообщения и генерации

POST /api/v1/chats создаёт диалог. GET /api/v1/chats возвращает доступные
авторизованному пользователю диалоги. GET /api/v1/chats/{chat}/messages читает
историю сообщений. POST /api/v1/chats/{chat}/messages принимает сообщение
и возвращает квитанцию генерации с HTTP 202, а не готовый ответ.
Запрос содержит content, expected_revision, use_memory и необязательный
reply_language. Idempotency-Key передаётся в request header.
GET /api/v1/generations/{generation} позволяет узнать состояние генерации;
GET /api/v1/generations/{generation}/events предоставляет event stream.

POST /api/v1/messages/{message}/retry создаёт явный повтор по правилам сервиса.
Retry не заменяет молча уже завершённый ответ модели.

## Настройки владельца и память

GET /api/v1/preferences читает настройки текущего owner.
PATCH /api/v1/preferences обновляет ui_language и reply_language с
expected_revision. Допустимы только ru и en.
POST /api/v1/memory/search выполняет лексический поиск памяти в рамках owner.
GET /api/v1/chats/{chat}/messages/{message}/context читает авторизованный context.

## Authentication и изоляция

Owner определяется authenticated identity, а не произвольным owner ID из
model-generated input. Неавторизованные и неизвестные chat/generation IDs
имеют одинаковое not-found поведение. API проверяет browser sessions, CSRF,
HTTPS origins и request limits. Private history не является источником Project RAG.

Языки UI и ответа задаются отдельно. Project RAG дня 31 читает документацию
API, а не работающий приватный API и не базу переписки.

Источники: day-30-private-ai-service/bublik_service/http_api.py;
day-30-private-ai-service/bublik_service/domain.py.
