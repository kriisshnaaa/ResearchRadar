CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    delivery_status TEXT NOT NULL DEFAULT 'not_attempted'
);
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    published_at TEXT,
    content_hash TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_topic TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_items (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    item_id TEXT NOT NULL REFERENCES items(id),
    duplicate_cluster_id TEXT,
    included_in_digest INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, item_id)
);
CREATE TABLE IF NOT EXISTS source_statuses (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    attempted INTEGER NOT NULL,
    success INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    error TEXT,
    PRIMARY KEY (run_id, source_type, source_name)
);
CREATE TABLE IF NOT EXISTS deliveries (
    run_id INTEGER PRIMARY KEY REFERENCES runs(id),
    status TEXT NOT NULL,
    parts_sent INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
