-- Additive migration: historical chats, jobs and idempotency stay intact.
CREATE TABLE browser_sessions (
    secret_hash TEXT PRIMARY KEY,
    owner_id TEXT REFERENCES users(id),
    csrf TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX sessions_expiry ON browser_sessions(expires_at);
CREATE TABLE api_tokens (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    secret_hash TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    scopes_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1))
);
CREATE TABLE rate_events (
    bucket TEXT NOT NULL,
    occurred_at REAL NOT NULL
);
CREATE INDEX rate_bucket_time ON rate_events(bucket,occurred_at);
-- Durable monotonically increasing snapshot IDs, without storing text deltas.
CREATE TABLE message_stream_versions (
    message_id TEXT PRIMARY KEY REFERENCES messages(id),
    version INTEGER NOT NULL DEFAULT 0
);
INSERT INTO message_stream_versions(message_id) SELECT id FROM messages;
CREATE TRIGGER message_stream_insert AFTER INSERT ON messages
BEGIN
    INSERT INTO message_stream_versions(message_id) VALUES (NEW.id);
END;
CREATE TRIGGER message_stream_update AFTER UPDATE OF content,status ON messages
WHEN OLD.content<>NEW.content OR OLD.status<>NEW.status
BEGIN
    UPDATE message_stream_versions SET version=version+1 WHERE message_id=NEW.id;
END;
