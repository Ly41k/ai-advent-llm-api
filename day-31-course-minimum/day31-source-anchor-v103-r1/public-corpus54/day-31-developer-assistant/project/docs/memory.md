# Memory and project knowledge / Память и знания проекта

## Original conversation history

The Day 30 private service stores original conversation messages in SQLite.
Conversation history is the primary source of truth. Search indexes are derived
caches and can be rebuilt without deleting original messages. Assistant messages
record what the assistant said; they are not automatically verified user facts.

Полная история переписки хранится в SQLite сервиса дня 30. Оригиналы сообщений не
заменяются краткими обобщениями. Индекс поиска можно пересоздать из оригиналов.
Личные диалоги и проектная документация остаются разными хранилищами.

## Lexical memory retrieval in Day 30

bublik_service/memory.py defines MemoryRetriever and a HistorySearch protocol.
The current implementation uses SQLite FTS5 and BM25 with unicode61 tokenization.
It searches accepted user messages and nonempty terminal assistant text for the
authenticated owner. Source snippets retain message/chat IDs, role, status,
date and source SHA-256. Up to three source fragments enter a generation snapshot.
The owner comes from authentication; callers do not select another user's owner ID.

Поиск памяти дня 30 — лексический FTS5. Он не использует дополнительную embedding
модель и не гарантирует поиск перефразировок между русским и английским языками.
Источники сверяются с оригинальными сообщениями перед admission. Ошибка поиска
не заменяется скрытым обычным ответом без памяти.

## Project RAG in Day 31

Project RAG searches explicitly selected README files, architecture documents
and permitted schema descriptions. It never reads the Day 30 chats.sqlite3,
memory-index or exported private conversation archives. Project index identity
contains project ID, corpus fingerprint, chunker version and embedding digest.

Day 31 can compare FTS5, bge-m3 dense retrieval and hybrid RRF on the same chunks.
Its vector index is not a new personal-memory layer. Implementing project dense
retrieval does not upgrade the Day 30 private chat's memory search.

## Language settings

Day 30 has separate owner preferences ui_language and reply_language, accepting
ru or en. The original message and source quotation keep their original text.
Language guidance is stored in the generation snapshot. Schema 3 adds language
preferences; history archive/restore supports the preceding supported schemas.

Sources: day-30-private-ai-service/bublik_service/memory.py;
day-30-private-ai-service/bublik_service/languages.py;
day-30-private-ai-service/bublik_service/storage/migrations/003_languages.sql.
