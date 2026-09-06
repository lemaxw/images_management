DROP TABLE IF EXISTS poem_first_place_usage;
DROP TABLE IF EXISTS poems;
CREATE TABLE poems (
        id TEXT PRIMARY KEY,
        text TEXT,
        entity TEXT,
        translation TEXT,
        author TEXT,
        link_to_source TEXT,
        rating NUMERIC,
        date_of_usage TIMESTAMP
    );

CREATE TABLE poem_first_place_usage (
        poem_id TEXT PRIMARY KEY REFERENCES poems(id) ON DELETE CASCADE,
        first_used_at TIMESTAMP NOT NULL
    );
