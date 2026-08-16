CREATE TABLE profiles_without_market (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    photo_ref TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO profiles_without_market(singleton_id, photo_ref, created_at, updated_at)
SELECT singleton_id, photo_ref, created_at, updated_at
FROM profiles
WHERE photo_ref IS NOT NULL;

DROP TABLE profiles;
ALTER TABLE profiles_without_market RENAME TO profiles;

UPDATE saved_looks
SET snapshot_json = json_remove(snapshot_json, '$.currency')
WHERE json_type(snapshot_json, '$.currency') IS NOT NULL;
