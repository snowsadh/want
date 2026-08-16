CREATE TABLE profiles (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    region TEXT NOT NULL CHECK (region IN ('us', 'in')),
    currency TEXT NOT NULL CHECK (currency IN ('USD', 'INR')),
    photo_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (region = 'us' AND currency = 'USD') OR
        (region = 'in' AND currency = 'INR')
    )
);

CREATE TABLE saved_looks (
    id TEXT PRIMARY KEY,
    source_url TEXT,
    capture_ref TEXT NOT NULL,
    personalized_result_ref TEXT,
    snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_saved_looks_created_at ON saved_looks(created_at DESC);
