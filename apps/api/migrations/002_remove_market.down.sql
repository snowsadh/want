CREATE TABLE profiles_with_market (
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

INSERT INTO profiles_with_market(
    singleton_id, region, currency, photo_ref, created_at, updated_at
)
SELECT singleton_id, 'us', 'USD', photo_ref, created_at, updated_at
FROM profiles;

DROP TABLE profiles;
ALTER TABLE profiles_with_market RENAME TO profiles;

UPDATE saved_looks
SET snapshot_json = json_set(snapshot_json, '$.currency', 'USD')
WHERE json_type(snapshot_json, '$.currency') IS NULL;
