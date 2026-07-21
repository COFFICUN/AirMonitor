PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_uid TEXT NOT NULL UNIQUE,
    name TEXT,
    created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS measurement_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    started_at_utc TEXT NOT NULL,
    ended_at_utc TEXT NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    center_latitude REAL,
    center_longitude REAL,
    avg_temperature REAL,
    avg_humidity REAL,
    avg_pm1 REAL,
    avg_pm25 REAL,
    avg_pm10 REAL,
    min_pm25 INTEGER,
    max_pm25 INTEGER,
    aqi_pm25 INTEGER,
    aqi_category TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

CREATE TABLE IF NOT EXISTS raw_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    sent_at_utc TEXT,
    received_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    temperature REAL,
    humidity REAL,
    pm1 INTEGER,
    pm25 INTEGER,
    pm10 INTEGER,
    pc0_3 INTEGER,
    pc0_5 INTEGER,
    pc1_0 INTEGER,
    pc2_5 INTEGER,
    pc5_0 INTEGER,
    pc10 INTEGER,
    latitude REAL,
    longitude REAL,
    is_valid INTEGER NOT NULL DEFAULT 1,
    validation_note TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

CREATE TABLE IF NOT EXISTS raw_session_links (
    raw_id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    FOREIGN KEY (raw_id) REFERENCES raw_measurements(id),
    FOREIGN KEY (session_id) REFERENCES measurement_sessions(id)
);

CREATE TABLE IF NOT EXISTS device_runtime_state (
    device_id INTEGER PRIMARY KEY,
    measurement_enabled INTEGER NOT NULL DEFAULT 0,
    active_session_id INTEGER,
    fixed_latitude REAL,
    fixed_longitude REAL,
    measurement_started_at_utc TEXT,
    location_updated_at_utc TEXT,
    updated_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (active_session_id) REFERENCES measurement_sessions(id)
);

CREATE TABLE IF NOT EXISTS aggregated_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    window_start_utc TEXT NOT NULL,
    window_end_utc TEXT NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    avg_temperature REAL,
    avg_humidity REAL,
    avg_pm1 REAL,
    avg_pm25 REAL,
    avg_pm10 REAL,
    min_pm25 INTEGER,
    max_pm25 INTEGER,
    aqi_pm25 INTEGER,
    aqi_category TEXT,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

CREATE INDEX IF NOT EXISTS idx_raw_device_sent_at
    ON raw_measurements(device_id, sent_at_utc);

CREATE INDEX IF NOT EXISTS idx_sessions_device_time
    ON measurement_sessions(device_id, started_at_utc, ended_at_utc);

CREATE INDEX IF NOT EXISTS idx_agg_device_window_end
    ON aggregated_measurements(device_id, window_end_utc);

INSERT OR IGNORE INTO devices (device_uid, name)
VALUES ('airmonitor-main', 'AirMonitor Main Device');
