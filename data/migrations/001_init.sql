CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    asset_type TEXT NOT NULL,
    name TEXT NOT NULL,
    owner TEXT,
    criticality INTEGER,
    environment TEXT,
    vendor TEXT,
    lifecycle_years INTEGER
);

CREATE TABLE IF NOT EXISTS risk_scores (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    scenario TEXT NOT NULL,
    score REAL NOT NULL
);
