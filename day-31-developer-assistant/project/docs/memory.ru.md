# Память и знания проекта

## Оригинальная история переписки дня 30

Приватный сервис дня 30 хранит оригинальные сообщения в SQLite. Полная история
переписки — основное хранилище. Поисковые индексы являются производными caches;
их можно пересоздать без удаления сообщений. Сохранённый текст ассистента —
запись того, что ассистент сказал. Он автоматически не становится проверенным
фактом о пользователе. Оригиналы не заменяются краткими обобщениями.
Личные диалоги и проектная документация остаются разными хранилищами.

## Лексический поиск личной памяти дня 30

bublik_service/memory.py определяет MemoryRetriever и протокол HistorySearch.
Текущая реализация использует SQLite FTS5, BM25 и unicode61. Она ищет принятые
user messages и непустой terminal assistant text только authenticated owner.
Источники сохраняют message/chat IDs, role, status, date и source SHA-256.
В generation snapshot входят до трёх фрагментов. Owner задаётся authentication;
caller не может выбрать owner ID другого пользователя.

Лексический поиск не использует дополнительную embedding-модель и не гарантирует
нахождение русско-английских перефразировок. Источники сверяются с оригинальными
сообщениями перед admission. Ошибка поиска не заменяется скрытым обычным ответом
без памяти.

## Project RAG дня 31 и личная память

Project RAG ищет по явно выбранным README, архитектурным документам и разрешённым
описаниям schemas. Он не читает Day 30 chats.sqlite3, memory-index и экспорты
личных архивов. Identity индекса содержит project ID, corpus fingerprint,
chunker version и embedding digest.

День 31 сравнивает FTS5, bge-m3 dense retrieval и hybrid RRF на одних чанках.
Векторный индекс проекта не является новым слоем личной памяти. Добавление dense
Project RAG дня 31 не делает поиск личной памяти дня 30 векторным и не обновляет
поиск приватного чата. Эти подсистемы отделены.

## Языковые настройки и исходный текст

День 30 хранит отдельные owner preferences ui_language и reply_language;
допустимые значения — ru и en. После смены языка оригинал сообщения и цитата
источника сохраняют исходный текст: они не переводятся и не заменяются переводом.
Language guidance сохраняется в generation snapshot. Schema 3 добавляет
языковые preferences; history archive/restore поддерживает предыдущие
поддержанные schemas.

Источники: day-30-private-ai-service/bublik_service/memory.py;
day-30-private-ai-service/bublik_service/languages.py;
day-30-private-ai-service/bublik_service/storage/migrations/003_languages.sql.
