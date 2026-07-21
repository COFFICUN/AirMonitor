from flask import Flask, request, render_template, g, jsonify, Response
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import csv
import io
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=BASE_DIR)
DATABASE = os.path.join(BASE_DIR, "sensor_data.db")

ALMATY_TZ = ZoneInfo("Asia/Almaty")
UTC = timezone.utc
DEVICE_UID = "airmonitor-main"
LOCATION_STALE_SECONDS = 30
MAX_ACTIVE_SESSION_HOURS = 8


# -----------------------------
# DB helpers
# -----------------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        ensure_runtime_tables(db)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def ensure_runtime_tables(db):
    db.execute(
        """
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
        )
        """
    )
    db.commit()


# -----------------------------
# Time helpers
# -----------------------------
def utc_now():
    return datetime.now(UTC)


def utc_now_str():
    return utc_now().strftime("%Y-%m-%d %H:%M:%S")


def parse_utc(ts_value):
    if not ts_value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(ts_value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def format_almaty(ts_value, fmt="%d.%m.%Y %H:%M:%S"):
    dt_utc = parse_utc(ts_value)
    if dt_utc is None:
        return None
    return dt_utc.astimezone(ALMATY_TZ).strftime(fmt)


def now_almaty_str(fmt="%d.%m.%Y %H:%M:%S"):
    return datetime.now(ALMATY_TZ).strftime(fmt)


def get_relative_update_text(total_seconds):
    if total_seconds is None:
        return "нет данных"
    if total_seconds < 60:
        return f"{int(total_seconds)} сек назад"
    minutes = int(total_seconds // 60)
    if minutes < 60:
        return f"{minutes} мин назад"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours} ч назад"
    days = int(hours // 24)
    return f"{days} дн назад"


def seconds_between(start_ts, end_ts):
    start = parse_utc(start_ts)
    end = parse_utc(end_ts)
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds()))


def humanize_duration(seconds):
    if seconds is None:
        return "—"
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} ч {minutes} мин"
    if minutes:
        return f"{minutes} мин {sec} сек"
    return f"{sec} сек"


# -----------------------------
# Generic helpers
# -----------------------------
def safe_round(value, digits=1):
    if value is None:
        return None
    return round(value, digits)


def average_or_none(values, digits=1):
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return round(sum(filtered) / len(filtered), digits)


def moving_average(values, window=5):
    if not values:
        return values
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = [v for v in values[start:i + 1] if v is not None]
        result.append(round(sum(chunk) / len(chunk), 1) if chunk else None)
    return result


# -----------------------------
# Device / runtime state
# -----------------------------
def get_device_id():
    row = get_db().execute(
        "SELECT id FROM devices WHERE device_uid = ?",
        (DEVICE_UID,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"Устройство {DEVICE_UID} не найдено в devices")
    return row["id"]


def ensure_runtime_row(device_id):
    db = get_db()
    db.execute("INSERT OR IGNORE INTO device_runtime_state (device_id) VALUES (?)", (device_id,))
    db.commit()


def get_runtime_state(device_id):
    ensure_runtime_row(device_id)
    row = get_db().execute(
        "SELECT * FROM device_runtime_state WHERE device_id = ?",
        (device_id,),
    ).fetchone()
    return dict(row) if row else None


def update_runtime_state(device_id, **fields):
    allowed = {
        "measurement_enabled",
        "active_session_id",
        "fixed_latitude",
        "fixed_longitude",
        "measurement_started_at_utc",
        "location_updated_at_utc",
        "updated_at_utc",
    }
    updates = []
    params = []
    for key, value in fields.items():
        if key in allowed:
            updates.append(f"{key} = ?")
            params.append(value)
    if not updates:
        return
    params.append(device_id)
    ensure_runtime_row(device_id)
    get_db().execute(
        f"UPDATE device_runtime_state SET {', '.join(updates)} WHERE device_id = ?",
        params,
    )
    get_db().commit()


def is_measurement_active(runtime_state):
    if not runtime_state:
        return False
    if int(runtime_state.get("measurement_enabled") or 0) != 1:
        return False
    if runtime_state.get("active_session_id") is None:
        return False
    if runtime_state.get("fixed_latitude") is None or runtime_state.get("fixed_longitude") is None:
        return False
    updated_at = parse_utc(runtime_state.get("location_updated_at_utc"))
    started_at = parse_utc(runtime_state.get("measurement_started_at_utc"))
    if updated_at is None or started_at is None:
        return False
    age = (utc_now() - updated_at).total_seconds()
    lifetime = (utc_now() - started_at).total_seconds()
    return age <= LOCATION_STALE_SECONDS and lifetime <= MAX_ACTIVE_SESSION_HOURS * 3600


def get_measurement_state_payload(device_id):
    runtime = get_runtime_state(device_id)
    active = is_measurement_active(runtime)
    session = None
    if runtime and runtime.get("active_session_id"):
        session = get_session_by_id(runtime["active_session_id"], device_id)

    started = runtime.get("measurement_started_at_utc") if runtime else None
    ended_reference = utc_now_str() if active else (session["ended_at_utc"] if session else None)
    duration_seconds = seconds_between(started, ended_reference)

    return {
        "measurement_enabled": active,
        "active_session_id": runtime.get("active_session_id") if active and runtime else None,
        "fixed_latitude": runtime.get("fixed_latitude") if active and runtime else None,
        "fixed_longitude": runtime.get("fixed_longitude") if active and runtime else None,
        "measurement_started_at_utc": started if active else None,
        "measurement_started_at_text": format_almaty(started) if active and started else None,
        "location_updated_at_utc": runtime.get("location_updated_at_utc") if active and runtime else None,
        "location_freshness_text": get_relative_update_text(max(0, int((utc_now() - parse_utc(runtime['location_updated_at_utc'])).total_seconds()))) if active and runtime and runtime.get("location_updated_at_utc") else "неактивно",
        "session_sample_count": session["sample_count"] if session else 0,
        "session_duration_seconds": duration_seconds,
        "session_duration_text": humanize_duration(duration_seconds),
    }


# -----------------------------
# Validation
# -----------------------------
def validate_payload(data):
    numeric_fields = [
        "temperature", "humidity", "pm1", "pm25", "pm10",
        "pc0_3", "pc0_5", "pc1_0", "pc2_5", "pc5_0", "pc10",
        "latitude", "longitude",
    ]
    cleaned = {field: data.get(field) for field in numeric_fields}

    for field in ["pm1", "pm25", "pm10", "pc0_3", "pc0_5", "pc1_0", "pc2_5", "pc5_0", "pc10"]:
        value = cleaned.get(field)
        if value is not None and value < 0:
            return False, "negative_particle_value"

    humidity = cleaned.get("humidity")
    if humidity is not None and not (0 <= humidity <= 100):
        return False, "humidity_out_of_range"

    temperature = cleaned.get("temperature")
    if temperature is not None and not (-40 <= temperature <= 85):
        return False, "temperature_out_of_range"

    latitude = cleaned.get("latitude")
    if latitude is not None and not (-90 <= latitude <= 90):
        return False, "latitude_out_of_range"

    longitude = cleaned.get("longitude")
    if longitude is not None and not (-180 <= longitude <= 180):
        return False, "longitude_out_of_range"

    return True, None


# -----------------------------
# AQI / PM science
# -----------------------------
def pm25_to_aqi_24h(pm25):
    if pm25 is None:
        return None
    breakpoints = [
        (0.0, 9.0, 0, 50),
        (9.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 125.4, 151, 200),
        (125.5, 225.4, 201, 300),
        (225.5, 325.4, 301, 400),
        (325.5, 500.4, 401, 500),
    ]
    c = round(float(pm25), 1)
    for c_lo, c_hi, i_lo, i_hi in breakpoints:
        if c_lo <= c <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (c - c_lo) + i_lo)
    return 500


def get_air_quality(pm25_value):
    if pm25_value is None:
        return {
            "label": "Нет данных",
            "short": "Нет данных",
            "color": "#7c8798",
            "class_name": "pill-neutral",
            "aqi": None,
            "recommendation": "Ожидаются новые измерения для оценки качества воздуха.",
            "risk": "не определён",
            "metric_label": "Локальная оценка по PM2.5",
        }
    pm = float(pm25_value)
    aqi = pm25_to_aqi_24h(pm)
    if pm <= 12:
        return {
            "label": "Низкий уровень загрязнения",
            "short": "Хорошее",
            "color": "#22c55e",
            "class_name": "pill-good",
            "aqi": aqi,
            "risk": "низкий",
            "recommendation": "Условия благоприятные для обычной активности на улице.",
            "metric_label": "Локальная оценка по PM2.5",
        }
    if pm <= 35:
        return {
            "label": "Умеренный уровень загрязнения",
            "short": "Умеренное",
            "color": "#f59e0b",
            "class_name": "pill-moderate",
            "aqi": aqi,
            "risk": "умеренный",
            "recommendation": "Чувствительным людям лучше сократить длительное пребывание у дорог.",
            "metric_label": "Локальная оценка по PM2.5",
        }
    if pm <= 55:
        return {
            "label": "Повышенное загрязнение",
            "short": "Повышенное",
            "color": "#f97316",
            "class_name": "pill-elevated",
            "aqi": aqi,
            "risk": "повышенный",
            "recommendation": "Желательно ограничить интенсивную активность на улице.",
            "metric_label": "Локальная оценка по PM2.5",
        }
    if pm <= 125:
        return {
            "label": "Вредный уровень загрязнения",
            "short": "Вредное",
            "color": "#ef4444",
            "class_name": "pill-bad",
            "aqi": aqi,
            "risk": "высокий",
            "recommendation": "Лучше сократить пребывание на улице и закрыть окна рядом с дорогами.",
            "metric_label": "Локальная оценка по PM2.5",
        }
    return {
        "label": "Очень вредный уровень загрязнения",
        "short": "Очень вредное",
        "color": "#8b5cf6",
        "class_name": "pill-severe",
        "aqi": aqi,
        "risk": "очень высокий",
        "recommendation": "Рекомендуется оставаться в помещении и минимизировать контакт с наружным воздухом.",
        "metric_label": "Локальная оценка по PM2.5",
    }


def classify_stability(min_pm25, max_pm25):
    if min_pm25 is None or max_pm25 is None:
        return {
            "label": "нет данных",
            "short": "нет данных",
            "spread": None,
            "class_name": "pill-neutral",
        }
    spread = float(max_pm25) - float(min_pm25)
    if spread < 10:
        return {
            "label": "стабильный воздух",
            "short": "стабильно",
            "spread": round(spread, 1),
            "class_name": "pill-good",
        }
    if spread <= 30:
        return {
            "label": "умеренные колебания",
            "short": "умеренно",
            "spread": round(spread, 1),
            "class_name": "pill-moderate",
        }
    return {
        "label": "нестабильное загрязнение",
        "short": "скачки",
        "spread": round(spread, 1),
        "class_name": "pill-bad",
    }


def build_hourly_pm25(device_id, hours=12):
    since = utc_now() - timedelta(hours=hours)
    rows = get_db().execute(
        """
        SELECT COALESCE(sent_at_utc, received_at_utc) AS ts, pm25
        FROM raw_measurements
        WHERE device_id = ?
          AND is_valid = 1
          AND pm25 IS NOT NULL
          AND COALESCE(sent_at_utc, received_at_utc) >= ?
        ORDER BY COALESCE(sent_at_utc, received_at_utc) ASC
        """,
        (device_id, since.strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchall()

    buckets = {}
    for row in rows:
        dt = parse_utc(row["ts"])
        if not dt:
            continue
        hour_key = dt.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:00:00")
        buckets.setdefault(hour_key, []).append(float(row["pm25"]))

    ordered_keys = sorted(buckets.keys())[-hours:]
    return [round(sum(buckets[k]) / len(buckets[k]), 1) for k in ordered_keys]


def compute_nowcast_pm25(hourly_values):
    values = [float(v) for v in hourly_values if v is not None]
    if len(values) < 3:
        return None
    c_max = max(values)
    c_min = min(values)
    if c_max <= 0:
        return 0.0
    weight_factor = c_min / c_max if c_max else 0.0
    weight_factor = max(0.5, weight_factor)

    weighted_sum = 0.0
    weight_total = 0.0
    n = len(values)
    for i, value in enumerate(values):
        exponent = n - 1 - i
        weight = weight_factor ** exponent
        weighted_sum += value * weight
        weight_total += weight

    return round(weighted_sum / weight_total, 1) if weight_total else None


def build_nowcast_payload(device_id):
    hourly = build_hourly_pm25(device_id, hours=12)
    nowcast_pm25 = compute_nowcast_pm25(hourly)
    aqi = pm25_to_aqi_24h(nowcast_pm25)
    quality = get_air_quality(nowcast_pm25)
    return {
        "hourly_points": hourly,
        "pm25": nowcast_pm25,
        "aqi": aqi,
        "quality": quality,
        "available": nowcast_pm25 is not None,
        "method": "EPA NowCast (приближённо по часовым средним)",
    }


# -----------------------------
# Empty session cleanup
# -----------------------------
def delete_session_if_empty(session_id, device_id):
    if not session_id:
        return False

    db = get_db()

    row = db.execute(
        """
        SELECT s.id, s.sample_count, COUNT(l.raw_id) AS linked_count
        FROM measurement_sessions s
        LEFT JOIN raw_session_links l ON l.session_id = s.id
        WHERE s.id = ? AND s.device_id = ?
        GROUP BY s.id, s.sample_count
        """,
        (session_id, device_id),
    ).fetchone()

    if not row:
        return False

    sample_count = row["sample_count"] or 0
    linked_count = row["linked_count"] or 0

    if sample_count > 0 or linked_count > 0:
        return False

    # Сначала убираем возможную ссылку из runtime-состояния
    db.execute(
        """
        UPDATE device_runtime_state
        SET measurement_enabled = 0,
            active_session_id = NULL,
            fixed_latitude = NULL,
            fixed_longitude = NULL,
            measurement_started_at_utc = NULL,
            location_updated_at_utc = NULL,
            updated_at_utc = ?
        WHERE device_id = ? AND active_session_id = ?
        """,
        (utc_now_str(), device_id, session_id),
    )

    try:
        db.execute(
            "DELETE FROM measurement_sessions WHERE id = ? AND device_id = ?",
            (session_id, device_id),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        db.rollback()
        return False


def cleanup_empty_sessions(device_id):
    db = get_db()

    rows = db.execute(
        """
        SELECT s.id
        FROM measurement_sessions s
        LEFT JOIN raw_session_links l ON l.session_id = s.id
        LEFT JOIN device_runtime_state rs ON rs.active_session_id = s.id
        WHERE s.device_id = ?
          AND rs.active_session_id IS NULL
        GROUP BY s.id, s.sample_count
        HAVING COALESCE(s.sample_count, 0) <= 0 AND COUNT(l.raw_id) = 0
        """,
        (device_id,),
    ).fetchall()

    deleted = 0

    for row in rows:
        try:
            db.execute(
                "DELETE FROM measurement_sessions WHERE id = ? AND device_id = ?",
                (row["id"], device_id),
            )
            deleted += 1
        except sqlite3.IntegrityError:
            # Если на сессию всё ещё есть ссылка из другой таблицы — просто пропускаем
            continue

    if deleted:
        db.commit()

    return deleted


# -----------------------------
# Queries / stats
# -----------------------------
def get_total_raw_records(device_id):
    row = get_db().execute("SELECT COUNT(*) AS total FROM raw_measurements WHERE device_id = ?", (device_id,)).fetchone()
    return row["total"] if row else 0


def get_total_sessions(device_id):
    row = get_db().execute("SELECT COUNT(*) AS total FROM measurement_sessions WHERE device_id = ? AND COALESCE(sample_count, 0) > 0", (device_id,)).fetchone()
    return row["total"] if row else 0


def get_latest_raw_row(device_id):
    return get_db().execute(
        """
        SELECT *
        FROM raw_measurements
        WHERE device_id = ?
        ORDER BY COALESCE(sent_at_utc, received_at_utc) DESC
        LIMIT 1
        """,
        (device_id,),
    ).fetchone()


def get_system_status_from_raw(latest_row):
    if latest_row is None:
        return {
            "label": "Нет данных",
            "state": "offline",
            "seconds_since_update": None,
            "freshness_text": "нет данных",
        }

    ts = latest_row["sent_at_utc"] or latest_row["received_at_utc"]
    latest_dt = parse_utc(ts)
    if latest_dt is None:
        return {
            "label": "Нет данных",
            "state": "offline",
            "seconds_since_update": None,
            "freshness_text": "нет данных",
        }

    total_seconds = max(0, int((utc_now() - latest_dt).total_seconds()))
    if total_seconds <= 10:
        state, label = "online", "Устройство онлайн"
    elif total_seconds <= 30:
        state, label = "idle", "Нестабильная связь"
    else:
        state, label = "offline", "Устройство офлайн"
    return {
        "label": label,
        "state": state,
        "seconds_since_update": total_seconds,
        "freshness_text": get_relative_update_text(total_seconds),
    }


def get_session_by_id(session_id, device_id):
    if not session_id:
        return None
    return get_db().execute(
        "SELECT * FROM measurement_sessions WHERE id = ? AND device_id = ?",
        (session_id, device_id),
    ).fetchone()


def get_latest_session(device_id):
    return get_db().execute(
        "SELECT * FROM measurement_sessions WHERE device_id = ? AND COALESCE(sample_count, 0) > 0 ORDER BY ended_at_utc DESC LIMIT 1",
        (device_id,),
    ).fetchone()


def get_latest_raw_for_session(session_id, device_id):
    if not session_id:
        return None
    return get_db().execute(
        """
        SELECT r.*
        FROM raw_measurements r
        JOIN raw_session_links l ON l.raw_id = r.id
        WHERE l.session_id = ? AND r.device_id = ?
        ORDER BY COALESCE(r.sent_at_utc, r.received_at_utc) DESC
        LIMIT 1
        """,
        (session_id, device_id),
    ).fetchone()


def session_row_to_measurement(row, latest_raw_particle_row=None):
    if row is None:
        return None
    local_quality = get_air_quality(row["avg_pm25"])
    stability = classify_stability(row["min_pm25"], row["max_pm25"])
    duration_seconds = seconds_between(row["started_at_utc"], row["ended_at_utc"])
    return {
        "timestamp": format_almaty(row["ended_at_utc"]),
        "date_text": format_almaty(row["ended_at_utc"], "%d.%m.%Y"),
        "time_text": format_almaty(row["ended_at_utc"], "%H:%M:%S"),
        "temperature": safe_round(row["avg_temperature"]),
        "humidity": safe_round(row["avg_humidity"]),
        "pm1": safe_round(row["avg_pm1"]),
        "pm25": safe_round(row["avg_pm25"]),
        "pm10": safe_round(row["avg_pm10"]),
        "pc0_3": latest_raw_particle_row["pc0_3"] if latest_raw_particle_row else None,
        "pc0_5": latest_raw_particle_row["pc0_5"] if latest_raw_particle_row else None,
        "pc1_0": latest_raw_particle_row["pc1_0"] if latest_raw_particle_row else None,
        "pc2_5": latest_raw_particle_row["pc2_5"] if latest_raw_particle_row else None,
        "pc5_0": latest_raw_particle_row["pc5_0"] if latest_raw_particle_row else None,
        "pc10": latest_raw_particle_row["pc10"] if latest_raw_particle_row else None,
        "latitude": row["center_latitude"],
        "longitude": row["center_longitude"],
        "sample_count": row["sample_count"],
        "air_quality": local_quality,
        "stability": stability,
        "session_id": row["id"],
        "started_at": format_almaty(row["started_at_utc"]),
        "ended_at": format_almaty(row["ended_at_utc"]),
        "duration_seconds": duration_seconds,
        "duration_text": humanize_duration(duration_seconds),
        "min_pm25": safe_round(row["min_pm25"]),
        "max_pm25": safe_round(row["max_pm25"]),
    }


def fetch_recent_sessions(device_id, limit=12):
    rows = get_db().execute(
        "SELECT * FROM measurement_sessions WHERE device_id = ? AND COALESCE(sample_count, 0) > 0 ORDER BY ended_at_utc DESC LIMIT ?",
        (device_id, limit),
    ).fetchall()
    result = []
    for row in rows:
        quality = get_air_quality(row["avg_pm25"])
        stability = classify_stability(row["min_pm25"], row["max_pm25"])
        duration_seconds = seconds_between(row["started_at_utc"], row["ended_at_utc"])
        result.append({
            "session_id": row["id"],
            "timestamp": format_almaty(row["ended_at_utc"]),
            "date_text": format_almaty(row["ended_at_utc"], "%d.%m.%Y"),
            "time_text": format_almaty(row["ended_at_utc"], "%H:%M:%S"),
            "started_at_text": format_almaty(row["started_at_utc"]),
            "ended_at_text": format_almaty(row["ended_at_utc"]),
            "duration_text": humanize_duration(duration_seconds),
            "temperature": safe_round(row["avg_temperature"]),
            "humidity": safe_round(row["avg_humidity"]),
            "pm25": safe_round(row["avg_pm25"]),
            "min_pm25": safe_round(row["min_pm25"]),
            "max_pm25": safe_round(row["max_pm25"]),
            "latitude": row["center_latitude"],
            "longitude": row["center_longitude"],
            "sample_count": row["sample_count"],
            "air_quality": quality,
            "stability": stability,
        })
    return result


def get_stats_24h_sessions(device_id):
    since = (utc_now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    return get_db().execute(
        """
        SELECT
            COUNT(*) AS records,
            AVG(avg_temperature) AS avg_temperature,
            MIN(avg_temperature) AS min_temperature,
            MAX(avg_temperature) AS max_temperature,
            AVG(avg_humidity) AS avg_humidity,
            MIN(avg_humidity) AS min_humidity,
            MAX(avg_humidity) AS max_humidity,
            AVG(avg_pm25) AS avg_pm25,
            MIN(avg_pm25) AS min_pm25,
            MAX(avg_pm25) AS max_pm25,
            MAX(ended_at_utc) AS last_timestamp
        FROM measurement_sessions
        WHERE device_id = ?
          AND COALESCE(sample_count, 0) > 0
          AND COALESCE(sample_count, 0) > 0
          AND ended_at_utc >= ?
        """,
        (device_id, since),
    ).fetchone()


def get_session_raw_rows(session_id, device_id, limit=240):
    return get_db().execute(
        """
        SELECT
            r.id,
            COALESCE(r.sent_at_utc, r.received_at_utc) AS ts,
            r.temperature,
            r.humidity,
            r.pm25
        FROM raw_measurements r
        JOIN raw_session_links l ON l.raw_id = r.id
        WHERE l.session_id = ?
          AND r.device_id = ?
          AND r.is_valid = 1
        ORDER BY COALESCE(r.sent_at_utc, r.received_at_utc) ASC
        LIMIT ?
        """,
        (session_id, device_id, limit),
    ).fetchall()


def build_chart_for_session(device_id, session_id, limit=96):
    rows = get_session_raw_rows(session_id, device_id, limit=limit)
    raw_pm25 = [safe_round(row["pm25"]) for row in rows]
    smooth_pm25 = moving_average(raw_pm25, window=5)
    result = []
    for idx, row in enumerate(rows):
        result.append({
            "timestamp": format_almaty(row["ts"], "%H:%M:%S"),
            "timestamp_full": format_almaty(row["ts"]),
            "temperature": safe_round(row["temperature"]),
            "humidity": safe_round(row["humidity"]),
            "pm25": smooth_pm25[idx],
            "pm25_raw": raw_pm25[idx],
            "aqi": pm25_to_aqi_24h(smooth_pm25[idx]),
        })
    return result


def compute_trend_and_forecast(chart_rows):
    pm_values = [r["pm25"] for r in chart_rows if r["pm25"] is not None]
    if len(pm_values) < 6:
        return {
            "direction": "недостаточно данных",
            "delta": None,
            "forecast_pm25": None,
            "forecast_aqi": None,
            "forecast_quality": get_air_quality(None),
        }

    window = min(10, len(pm_values) // 2)
    recent = pm_values[-window:]
    previous = pm_values[-(window * 2):-window] if len(pm_values) >= window * 2 else pm_values[:-window]
    prev_avg = sum(previous) / len(previous) if previous else recent[0]
    recent_avg = sum(recent) / len(recent)
    delta = recent_avg - prev_avg

    if delta > 3:
        direction = "рост загрязнения"
    elif delta < -3:
        direction = "снижение загрязнения"
    else:
        direction = "стабильный уровень"

    subset = pm_values[-min(12, len(pm_values)):]
    n = len(subset)
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(subset) / n
    denom = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, subset)) / denom if denom else 0
    future_x = n + 3
    forecast = max(0, round(y_mean + slope * (future_x - x_mean), 1))
    return {
        "direction": direction,
        "delta": round(delta, 1),
        "forecast_pm25": forecast,
        "forecast_aqi": pm25_to_aqi_24h(forecast),
        "forecast_quality": get_air_quality(forecast),
    }


def aggregate_map_points_from_sessions(device_id, period="24h", max_markers=100):
    where = ["device_id = ?", "COALESCE(sample_count, 0) > 0", "center_latitude IS NOT NULL", "center_longitude IS NOT NULL"]
    params = [device_id]
    if period == "30m":
        since = utc_now() - timedelta(minutes=30)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    elif period == "1h":
        since = utc_now() - timedelta(hours=1)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    elif period == "24h":
        since = utc_now() - timedelta(hours=24)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    elif period != "all":
        since = utc_now() - timedelta(hours=24)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))

    clause = " AND ".join(where)
    rows = get_db().execute(
        f"SELECT * FROM measurement_sessions WHERE {clause} ORDER BY ended_at_utc DESC LIMIT ?",
        (*params, max_markers),
    ).fetchall()

    if not rows:
        return [], {
            "point_count": 0,
            "last_coordinates": None,
            "avg_pm25": None,
            "max_pm25": None,
            "generated_at": now_almaty_str(),
        }

    points = []
    for idx, row in enumerate(rows):
        quality = get_air_quality(row["avg_pm25"])
        points.append({
            "session_id": row["id"],
            "latitude": row["center_latitude"],
            "longitude": row["center_longitude"],
            "count": row["sample_count"],
            "pm25": safe_round(row["avg_pm25"]),
            "pm25_peak": row["max_pm25"],
            "temperature": safe_round(row["avg_temperature"]),
            "humidity": safe_round(row["avg_humidity"]),
            "timestamp": format_almaty(row["ended_at_utc"]),
            "air_quality": quality,
            "aqi": quality["aqi"],
            "radius": max(18, min(44, 16 + ((row["avg_pm25"] or 0) * 0.25))),
            "intensity": max(0.16, min(0.72, 0.18 + (((row["avg_pm25"] or 0) / 220)))),
            "is_latest": idx == 0,
        })

    pm_values = [p["pm25"] for p in points if p["pm25"] is not None]
    summary = {
        "point_count": len(points),
        "last_coordinates": {
            "latitude": round(points[0]["latitude"], 6),
            "longitude": round(points[0]["longitude"], 6),
        } if points else None,
        "avg_pm25": round(sum(pm_values) / len(pm_values), 1) if pm_values else None,
        "max_pm25": max(pm_values) if pm_values else None,
        "generated_at": now_almaty_str(),
    }
    return points, summary


def get_route_points_from_sessions(device_id, period="24h", limit=160):
    where = ["device_id = ?", "COALESCE(sample_count, 0) > 0", "center_latitude IS NOT NULL", "center_longitude IS NOT NULL"]
    params = [device_id]
    if period == "30m":
        since = utc_now() - timedelta(minutes=30)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    elif period == "1h":
        since = utc_now() - timedelta(hours=1)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    elif period == "24h":
        since = utc_now() - timedelta(hours=24)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
    elif period != "all":
        since = utc_now() - timedelta(hours=24)
        where.append("ended_at_utc >= ?")
        params.append(since.strftime("%Y-%m-%d %H:%M:%S"))

    rows = get_db().execute(
        f"SELECT * FROM measurement_sessions WHERE {' AND '.join(where)} ORDER BY ended_at_utc ASC LIMIT ?",
        (*params, limit),
    ).fetchall()
    return [{
        "session_id": row["id"],
        "latitude": row["center_latitude"],
        "longitude": row["center_longitude"],
        "timestamp": format_almaty(row["ended_at_utc"]),
        "time_text": format_almaty(row["ended_at_utc"], "%H:%M:%S"),
        "pm25": safe_round(row["avg_pm25"]),
        "temperature": safe_round(row["avg_temperature"]),
        "humidity": safe_round(row["avg_humidity"]),
        "aqi": pm25_to_aqi_24h(row["avg_pm25"]),
    } for row in rows]


# -----------------------------
# Session lifecycle
# -----------------------------
def create_new_session(device_id, sent_at_utc, latitude, longitude):
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO measurement_sessions (
            device_id, started_at_utc, ended_at_utc, sample_count,
            center_latitude, center_longitude,
            avg_temperature, avg_humidity, avg_pm1, avg_pm25, avg_pm10,
            min_pm25, max_pm25, aqi_pm25, aqi_category
        ) VALUES (?, ?, ?, 0, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?)
        """,
        (device_id, sent_at_utc, sent_at_utc, latitude, longitude, "Нет данных"),
    )
    db.commit()
    return cur.lastrowid


def rebuild_session_summary(session_id, device_id):
    db = get_db()
    rows = db.execute(
        """
        SELECT r.*
        FROM raw_measurements r
        JOIN raw_session_links l ON l.raw_id = r.id
        WHERE l.session_id = ? AND r.device_id = ? AND r.is_valid = 1
        ORDER BY COALESCE(r.sent_at_utc, r.received_at_utc) ASC
        """,
        (session_id, device_id),
    ).fetchall()
    if not rows:
        return

    last_ts = rows[-1]["sent_at_utc"] or rows[-1]["received_at_utc"]
    avg_temperature = average_or_none([row["temperature"] for row in rows], 1)
    avg_humidity = average_or_none([row["humidity"] for row in rows], 1)
    avg_pm1 = average_or_none([row["pm1"] for row in rows], 1)
    avg_pm25 = average_or_none([row["pm25"] for row in rows], 1)
    avg_pm10 = average_or_none([row["pm10"] for row in rows], 1)
    pm25_values = [row["pm25"] for row in rows if row["pm25"] is not None]
    min_pm25 = min(pm25_values) if pm25_values else None
    max_pm25 = max(pm25_values) if pm25_values else None

    lat_values = [row["latitude"] for row in rows if row["latitude"] not in (None, 0.0)]
    lon_values = [row["longitude"] for row in rows if row["longitude"] not in (None, 0.0)]
    center_latitude = round(sum(lat_values) / len(lat_values), 6) if lat_values else None
    center_longitude = round(sum(lon_values) / len(lon_values), 6) if lon_values else None

    quality = get_air_quality(avg_pm25)
    db.execute(
        """
        UPDATE measurement_sessions
        SET ended_at_utc = ?, sample_count = ?, center_latitude = ?, center_longitude = ?,
            avg_temperature = ?, avg_humidity = ?, avg_pm1 = ?, avg_pm25 = ?, avg_pm10 = ?,
            min_pm25 = ?, max_pm25 = ?, aqi_pm25 = ?, aqi_category = ?
        WHERE id = ? AND device_id = ?
        """,
        (
            last_ts, len(rows), center_latitude, center_longitude,
            avg_temperature, avg_humidity, avg_pm1, avg_pm25, avg_pm10,
            min_pm25, max_pm25, quality["aqi"], quality["short"],
            session_id, device_id,
        ),
    )
    db.commit()


def start_measurement(device_id, latitude, longitude):
    runtime = get_runtime_state(device_id)
    if is_measurement_active(runtime):
        return {
            "session_id": runtime["active_session_id"],
            "message": "Замер уже активен",
            "already_active": True,
        }
    started_at = utc_now_str()
    session_id = create_new_session(device_id, started_at, latitude, longitude)
    update_runtime_state(
        device_id,
        measurement_enabled=1,
        active_session_id=session_id,
        fixed_latitude=latitude,
        fixed_longitude=longitude,
        measurement_started_at_utc=started_at,
        location_updated_at_utc=started_at,
        updated_at_utc=started_at,
    )
    return {
        "session_id": session_id,
        "message": "Замер запущен",
        "already_active": False,
    }


def stop_measurement(device_id):
    runtime = get_runtime_state(device_id)
    active_session_id = runtime.get("active_session_id") if runtime else None

    if active_session_id:
        rebuild_session_summary(active_session_id, device_id)

    update_runtime_state(
        device_id,
        measurement_enabled=0,
        active_session_id=None,
        fixed_latitude=None,
        fixed_longitude=None,
        measurement_started_at_utc=None,
        location_updated_at_utc=None,
        updated_at_utc=utc_now_str(),
    )

    if active_session_id:
        delete_session_if_empty(active_session_id, device_id)

    return {
        "session_id": active_session_id,
        "message": "Замер завершён" if active_session_id else "Активная сессия не найдена",
    }


# -----------------------------
# Payload builder
# -----------------------------
def build_live_payload():
    device_id = get_device_id()
    cleanup_empty_sessions(device_id)
    latest_raw = get_latest_raw_row(device_id)
    latest_session = get_latest_session(device_id)
    latest_raw_particles = get_latest_raw_for_session(latest_session["id"], device_id) if latest_session else None
    latest = session_row_to_measurement(latest_session, latest_raw_particles)
    stats = get_stats_24h_sessions(device_id)
    recent = fetch_recent_sessions(device_id, 12)
    measurement_state = get_measurement_state_payload(device_id)
    chart_rows = build_chart_for_session(device_id, latest_session["id"], limit=96) if latest_session else []
    trend = compute_trend_and_forecast(chart_rows)
    nowcast = build_nowcast_payload(device_id)
    return {
        "latest": latest,
        "air_quality": latest["air_quality"] if latest else get_air_quality(None),
        "nowcast": nowcast,
        "measurement_state": measurement_state,
        "system_status": get_system_status_from_raw(latest_raw),
        "total_records": get_total_raw_records(device_id),
        "total_sessions": get_total_sessions(device_id),
        "stats": {
            "records": stats["records"] or 0,
            "avg_temperature": safe_round(stats["avg_temperature"]),
            "min_temperature": safe_round(stats["min_temperature"]),
            "max_temperature": safe_round(stats["max_temperature"]),
            "avg_humidity": safe_round(stats["avg_humidity"]),
            "min_humidity": safe_round(stats["min_humidity"]),
            "max_humidity": safe_round(stats["max_humidity"]),
            "avg_pm25": safe_round(stats["avg_pm25"]),
            "min_pm25": safe_round(stats["min_pm25"]),
            "max_pm25": safe_round(stats["max_pm25"]),
            "last_timestamp": format_almaty(stats["last_timestamp"]) if stats and stats["last_timestamp"] else None,
        },
        "trend": trend,
        "recent": recent,
        "generated_at": now_almaty_str(),
    }


# -----------------------------
# Routes
# -----------------------------
@app.route("/start_measurement", methods=["POST"])
def start_measurement_route():
    device_id = get_device_id()
    data = request.get_json(silent=True) or {}
    if "latitude" not in data or "longitude" not in data:
        return jsonify({"error": "bad data", "message": "Нужны latitude и longitude"}), 400
    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    is_valid, validation_note = validate_payload({"latitude": latitude, "longitude": longitude})
    if not is_valid:
        return jsonify({"error": validation_note}), 400
    result = start_measurement(device_id, latitude, longitude)
    return jsonify({"status": "ok", **result, "measurement_state": get_measurement_state_payload(device_id)}), 200


@app.route("/stop_measurement", methods=["POST"])
def stop_measurement_route():
    device_id = get_device_id()
    result = stop_measurement(device_id)
    return jsonify({"status": "ok", **result, "measurement_state": get_measurement_state_payload(device_id)}), 200


@app.route("/update_location", methods=["POST"])
def update_location_route():
    device_id = get_device_id()
    data = request.get_json(silent=True) or {}
    if "latitude" not in data or "longitude" not in data:
        return jsonify({"error": "bad data"}), 400
    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    runtime = get_runtime_state(device_id)
    if is_measurement_active(runtime):
        update_runtime_state(device_id, location_updated_at_utc=utc_now_str(), updated_at_utc=utc_now_str())
        return jsonify({"status": "already_active", "session_id": runtime["active_session_id"], "measurement_state": get_measurement_state_payload(device_id)}), 200
    result = start_measurement(device_id, latitude, longitude)
    return jsonify({"status": "success", **result, "measurement_state": get_measurement_state_payload(device_id)}), 200


@app.route("/api/measurement-status")
def api_measurement_status():
    device_id = get_device_id()
    return jsonify(get_measurement_state_payload(device_id))


@app.route("/api/location-status")
def api_location_status():
    device_id = get_device_id()
    state = get_measurement_state_payload(device_id)
    return jsonify({
        "location_ready": state["measurement_enabled"],
        "measurement_enabled": state["measurement_enabled"],
        "active_session_id": state["active_session_id"],
        "latitude": state["fixed_latitude"],
        "longitude": state["fixed_longitude"],
        "measurement_started_at_utc": state["measurement_started_at_utc"],
        "measurement_started_at_text": state["measurement_started_at_text"],
        "location_freshness_text": state["location_freshness_text"],
        "session_sample_count": state["session_sample_count"],
        "session_duration_text": state["session_duration_text"],
    })


@app.route("/update", methods=["POST"])
def update():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data"}), 400
    device_id = get_device_id()
    runtime = get_runtime_state(device_id)
    if not is_measurement_active(runtime):
        return jsonify({
            "status": "waiting_for_measurement_start",
            "message": "Замер не активирован. На сайте нажмите 'Начать замер' и получите геолокацию.",
        }), 409
    latitude = runtime["fixed_latitude"]
    longitude = runtime["fixed_longitude"]
    session_id = runtime["active_session_id"]
    sent_at_utc = data.get("sent_at_utc") or utc_now_str()
    is_valid, validation_note = validate_payload({**data, "latitude": latitude, "longitude": longitude})
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO raw_measurements (
            device_id, sent_at_utc, received_at_utc,
            temperature, humidity, pm1, pm25, pm10,
            pc0_3, pc0_5, pc1_0, pc2_5, pc5_0, pc10,
            latitude, longitude, is_valid, validation_note
        ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            device_id, sent_at_utc,
            data.get("temperature"), data.get("humidity"), data.get("pm1"), data.get("pm25"), data.get("pm10"),
            data.get("pc0_3"), data.get("pc0_5"), data.get("pc1_0"), data.get("pc2_5"), data.get("pc5_0"), data.get("pc10"),
            latitude, longitude, 1 if is_valid else 0, validation_note,
        ),
    )
    raw_id = cursor.lastrowid
    db.execute("INSERT OR REPLACE INTO raw_session_links (raw_id, session_id) VALUES (?, ?)", (raw_id, session_id))
    db.commit()
    rebuild_session_summary(session_id, device_id)
    update_runtime_state(device_id, location_updated_at_utc=utc_now_str(), updated_at_utc=utc_now_str())
    return jsonify({"status": "ok", "is_valid": is_valid, "validation_note": validation_note, "session_id": session_id}), 200


@app.route("/api/live")
def api_live():
    return jsonify(build_live_payload())


@app.route("/api/chart")
def api_chart():
    device_id = get_device_id()
    limit = max(12, min(request.args.get("limit", default=96, type=int), 500))
    runtime = get_runtime_state(device_id)
    session_id = runtime.get("active_session_id") if is_measurement_active(runtime) else None
    if not session_id:
        latest_session = get_latest_session(device_id)
        session_id = latest_session["id"] if latest_session else None
    chart_rows = build_chart_for_session(device_id, session_id, limit=limit) if session_id else []
    return jsonify({"chart": chart_rows, "trend": compute_trend_and_forecast(chart_rows), "generated_at": now_almaty_str(), "session_id": session_id})


@app.route("/api/map")
def api_map():
    device_id = get_device_id()
    period = request.args.get("period", default="24h", type=str)
    points, summary = aggregate_map_points_from_sessions(device_id, period=period)
    route_points = get_route_points_from_sessions(device_id, period=period)
    return jsonify({"map_points": points, "route_points": route_points, "map_summary": summary, "generated_at": now_almaty_str(), "period": period})


@app.route("/api/nowcast")
def api_nowcast():
    device_id = get_device_id()
    payload = build_nowcast_payload(device_id)
    payload["generated_at"] = now_almaty_str()
    return jsonify(payload)


@app.route("/export/csv")
def export_csv():
    device_id = get_device_id()
    rows = get_db().execute(
        """
        SELECT started_at_utc, ended_at_utc, sample_count, center_latitude, center_longitude,
               avg_temperature, avg_humidity, avg_pm1, avg_pm25, avg_pm10,
               min_pm25, max_pm25, aqi_pm25, aqi_category
        FROM measurement_sessions
        WHERE device_id = ?
          AND COALESCE(sample_count, 0) > 0
        ORDER BY ended_at_utc DESC
        """,
        (device_id,),
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "started_at_almaty", "ended_at_almaty", "duration_text", "sample_count", "latitude", "longitude",
        "avg_temperature_c", "avg_humidity_percent", "avg_pm1", "avg_pm25", "avg_pm10",
        "min_pm25", "max_pm25", "stability", "local_air_quality", "aqi_pm25",
    ])
    for row in rows:
        stability = classify_stability(row["min_pm25"], row["max_pm25"])
        quality = get_air_quality(row["avg_pm25"])
        writer.writerow([
            format_almaty(row["started_at_utc"]),
            format_almaty(row["ended_at_utc"]),
            humanize_duration(seconds_between(row["started_at_utc"], row["ended_at_utc"])),
            row["sample_count"], row["center_latitude"], row["center_longitude"],
            row["avg_temperature"], row["avg_humidity"], row["avg_pm1"], row["avg_pm25"], row["avg_pm10"],
            row["min_pm25"], row["max_pm25"], stability["label"], quality["short"], row["aqi_pm25"],
        ])
    filename = f"airmonitor_sessions_{datetime.now(ALMATY_TZ).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename={filename}'})


@app.route("/health")
def health():
    device_id = get_device_id()
    runtime = get_measurement_state_payload(device_id)
    latest_raw = get_latest_raw_row(device_id)
    latest_session = get_latest_session(device_id)
    return jsonify({
        "status": "ok",
        "device_uid": DEVICE_UID,
        "device_id": device_id,
        "measurement_state": runtime,
        "total_records": get_total_raw_records(device_id),
        "total_sessions": get_total_sessions(device_id),
        "last_raw_timestamp": latest_raw["sent_at_utc"] if latest_raw else None,
        "last_session_end": latest_session["ended_at_utc"] if latest_session else None,
        "generated_at": now_almaty_str(),
    })


@app.route("/")
def index():
    device_id = get_device_id()
    payload = build_live_payload()
    latest_session = get_latest_session(device_id)
    map_points, map_summary = aggregate_map_points_from_sessions(device_id, "24h")
    route_points = get_route_points_from_sessions(device_id, "24h")
    chart_rows = build_chart_for_session(device_id, latest_session["id"], limit=96) if latest_session else []
    return render_template(
        "index.html",
        latest=payload["latest"],
        air_quality=payload["air_quality"],
        nowcast=payload["nowcast"],
        system_status=payload["system_status"],
        measurement_state=payload["measurement_state"],
        stats=payload["stats"],
        total_records=payload["total_records"],
        total_sessions=payload["total_sessions"],
        recent_rows=payload["recent"],
        chart_rows=chart_rows,
        trend=payload["trend"],
        map_points=map_points,
        route_points=route_points,
        map_summary=map_summary,
        generated_at=payload["generated_at"],
    )


if __name__ == "__main__":
    cert_file = os.path.join(BASE_DIR, "172.20.10.4+2.pem")
    key_file = os.path.join(BASE_DIR, "172.20.10.4+2-key.pem")
    print("\n✅ AirMonitor запущен!")
    print("🌍 Открывай: https://172.20.10.4:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, ssl_context=(cert_file, key_file), use_reloader=False)
