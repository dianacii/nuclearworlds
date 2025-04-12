-- sqlite3 scores.db < create.sql

CREATE TABLE IF NOT EXISTS game_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    public_acceptance INTEGER,
    tech_advancement INTEGER,
    risk_of_nuclear_disaster INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
