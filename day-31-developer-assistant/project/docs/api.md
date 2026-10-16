# Private service API / API приватного сервиса

## API prefix and health

Day 30 defines PREFIX=/api/v1 in bublik_service/http_api.py.
GET /api/v1/health/live is a liveness endpoint. Readiness is available at
GET /api/v1/health/ready. Liveness alone does not verify successful Qwen generation.

## Chats, messages and generations

POST /api/v1/chats creates a conversation. GET /api/v1/chats lists authorized
conversations. GET /api/v1/chats/{chat}/messages reads message history.
POST /api/v1/chats/{chat}/messages accepts a new message and returns a generation
receipt with HTTP 202. The request includes content, expected_revision, use_memory
and optional reply_language. Idempotency-Key is passed as a request header.
GET /api/v1/generations/{generation} reads generation state.
GET /api/v1/generations/{generation}/events provides the generation event stream.

POST /api/v1/messages/{message}/retry creates an explicit retry under the service
rules. A retry is not a silent replacement of an already completed model answer.

## Preferences and memory

GET /api/v1/preferences reads the current owner's preferences.
PATCH /api/v1/preferences updates ui_language and reply_language with an
expected_revision. Only ru and en are valid language values.
POST /api/v1/memory/search performs owner-scoped lexical memory retrieval.
GET /api/v1/chats/{chat}/messages/{message}/context reads an authorized context.

## Authentication and isolation

The authenticated identity determines the owner; arbitrary owner IDs are not
accepted from model-generated input. Unauthorized and unknown chat/generation
IDs use the same not-found behavior. Browser sessions, CSRF, HTTPS origins and
request limits are enforced by the API. Private history is not exposed as a
Project RAG data source.

Префикс API — /api/v1. Языки интерфейса и ответа задаются отдельно: ui_language
и reply_language. Project RAG дня 31 читает документацию об API, а не обращения
к работающему приватному API и не базу переписки.

Sources: day-30-private-ai-service/bublik_service/http_api.py;
day-30-private-ai-service/bublik_service/domain.py.
