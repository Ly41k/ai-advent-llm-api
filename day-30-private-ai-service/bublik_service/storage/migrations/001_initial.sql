CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE chats (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX chats_by_owner ON chats(owner_id, created_at, id);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chats(id),
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (chat_id, sequence),
    UNIQUE (id, chat_id),
    CHECK ((role = 'user' AND status = 'accepted') OR
           (role = 'assistant' AND status IN
            ('queued', 'running', 'completed', 'truncated', 'failed', 'interrupted')))
);

CREATE TABLE generations (
    queue_order INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    chat_id TEXT NOT NULL REFERENCES chats(id),
    user_message_id TEXT NOT NULL,
    assistant_message_id TEXT NOT NULL UNIQUE,
    attempt INTEGER NOT NULL CHECK (attempt > 0),
    status TEXT NOT NULL CHECK (status IN
        ('queued', 'running', 'completed', 'truncated', 'failed', 'interrupted')),
    base_revision INTEGER NOT NULL CHECK (base_revision >= 0),
    profile_json TEXT NOT NULL,
    context_json TEXT NOT NULL,
    worker_token TEXT,
    error_code TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    UNIQUE (user_message_id, attempt),
    FOREIGN KEY (user_message_id, chat_id) REFERENCES messages(id, chat_id),
    FOREIGN KEY (assistant_message_id, chat_id) REFERENCES messages(id, chat_id),
    CHECK ((status = 'queued' AND worker_token IS NULL AND started_at IS NULL AND finished_at IS NULL) OR
           (status = 'running' AND worker_token IS NOT NULL AND started_at IS NOT NULL AND finished_at IS NULL) OR
           (status IN ('completed', 'truncated', 'failed', 'interrupted') AND finished_at IS NOT NULL)),
    CHECK ((status = 'failed' AND error_code IS NOT NULL) OR
           (status = 'interrupted' AND error_code IS NOT NULL) OR
           (status IN ('queued', 'running', 'completed', 'truncated') AND error_code IS NULL))
);
CREATE UNIQUE INDEX one_outstanding_per_chat ON generations(chat_id)
    WHERE status IN ('queued', 'running');
CREATE UNIQUE INDEX one_running_globally ON generations((1)) WHERE status = 'running';
CREATE UNIQUE INDEX one_completed_answer_per_question ON generations(user_message_id)
    WHERE status = 'completed';
CREATE INDEX queued_generations ON generations(status, queue_order);

CREATE TRIGGER generation_roles BEFORE INSERT ON generations
WHEN (SELECT role FROM messages WHERE id=NEW.user_message_id) != 'user'
  OR (SELECT role FROM messages WHERE id=NEW.assistant_message_id) != 'assistant'
BEGIN
    SELECT RAISE(ABORT, 'generation_message_role_mismatch');
END;

CREATE TABLE service_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    inference_uncertain INTEGER NOT NULL DEFAULT 0 CHECK (inference_uncertain IN (0, 1))
);
INSERT INTO service_state(id) VALUES (1);

CREATE TABLE idempotency (
    owner_id TEXT NOT NULL REFERENCES users(id),
    operation TEXT NOT NULL,
    request_key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, operation, request_key)
);

CREATE TABLE chat_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL REFERENCES chats(id),
    generation_id TEXT REFERENCES generations(id),
    kind TEXT NOT NULL CHECK (kind IN ('accepted', 'claimed', 'finished', 'recovered', 'expired')),
    created_at TEXT NOT NULL
);
