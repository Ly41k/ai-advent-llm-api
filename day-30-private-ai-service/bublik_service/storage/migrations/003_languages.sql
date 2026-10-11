-- Additive preferences; original messages, receipts and snapshots are untouched.
CREATE TABLE user_preferences (
    owner_id TEXT PRIMARY KEY REFERENCES users(id),
    ui_language TEXT NOT NULL DEFAULT 'ru' CHECK(ui_language IN ('ru','en')),
    reply_language TEXT NOT NULL DEFAULT 'ru' CHECK(reply_language IN ('ru','en')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0)
);
INSERT INTO user_preferences(owner_id) SELECT id FROM users;
CREATE TRIGGER user_preferences_insert AFTER INSERT ON users
BEGIN
    INSERT INTO user_preferences(owner_id) VALUES (NEW.id);
END;
