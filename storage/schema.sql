-- SQL schema for storage

-- SQLite schema for http cache
CREATE TABLE IF NOT EXISTS http_cache (
    key TEXT PRIMARY KEY,
    response TEXT,
    status INTEGER,
    timestamp REAL
);
