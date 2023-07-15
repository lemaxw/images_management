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
