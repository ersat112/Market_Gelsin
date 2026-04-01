import hashlib
import json
import os
import threading
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .normalization import normalize_barcode
from .runtime_db import connect_runtime as connect
from .storage import DEFAULT_DB_PATH


DEFAULT_FIREBASE_COLLECTION = "market_gelsin_barcode_scans"
DEFAULT_SOURCE_APP = "barkod_analiz"
MAX_BATCH_SIZE = 500
RECOGNIZED_EVENT_FIELDS = {
    "event_id",
    "barcode",
    "city_code",
    "city_plate_code",
    "signal_date",
    "scanned_at",
    "scan_count",
    "source_app",
    "device_id",
    "session_id",
    "user_id",
    "payload",
    "metadata",
    "context",
    "rebuild_hot_refresh",
}

INGEST_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS barcode_scan_signals (
    signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL DEFAULT 0,
    signal_date TEXT NOT NULL,
    scan_count INTEGER NOT NULL,
    source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (barcode, city_plate_code, signal_date, source_app)
);

CREATE TABLE IF NOT EXISTS barcode_scan_events (
    event_id TEXT PRIMARY KEY,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL DEFAULT 0,
    signal_date TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    scan_count INTEGER NOT NULL DEFAULT 1,
    source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
    device_id TEXT,
    session_id TEXT,
    user_id TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hot_product_refresh_candidates (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL,
    market_key TEXT NOT NULL,
    scan_count INTEGER NOT NULL,
    matched_offer_count INTEGER NOT NULL DEFAULT 0,
    execution_mode TEXT NOT NULL,
    refresh_interval_hours INTEGER NOT NULL,
    refresh_due_at TEXT NOT NULL,
    last_signal_at TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (barcode, city_plate_code, market_key)
);

CREATE INDEX IF NOT EXISTS idx_barcode_scan_signals_barcode_city_date
ON barcode_scan_signals(barcode, city_plate_code, signal_date);

CREATE INDEX IF NOT EXISTS idx_barcode_scan_events_barcode_city_date
ON barcode_scan_events(barcode, city_plate_code, signal_date);

CREATE INDEX IF NOT EXISTS idx_hot_refresh_candidates_status_due
ON hot_product_refresh_candidates(status, refresh_due_at, priority_score);
"""

INGEST_SCHEMA_PG_SQL = """
CREATE TABLE IF NOT EXISTS barcode_scan_signals (
    signal_id BIGSERIAL PRIMARY KEY,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL DEFAULT 0,
    signal_date DATE NOT NULL,
    scan_count INTEGER NOT NULL,
    source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (barcode, city_plate_code, signal_date, source_app)
);

CREATE TABLE IF NOT EXISTS barcode_scan_events (
    event_id TEXT PRIMARY KEY,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL DEFAULT 0,
    signal_date DATE NOT NULL,
    scanned_at TIMESTAMPTZ NOT NULL,
    scan_count INTEGER NOT NULL DEFAULT 1,
    source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
    device_id TEXT,
    session_id TEXT,
    user_id TEXT,
    payload_json TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS hot_product_refresh_candidates (
    candidate_id BIGSERIAL PRIMARY KEY,
    barcode TEXT NOT NULL,
    city_plate_code INTEGER NOT NULL,
    market_key TEXT NOT NULL,
    scan_count INTEGER NOT NULL,
    matched_offer_count INTEGER NOT NULL DEFAULT 0,
    execution_mode TEXT NOT NULL,
    refresh_interval_hours INTEGER NOT NULL,
    refresh_due_at TIMESTAMPTZ NOT NULL,
    last_signal_at TIMESTAMPTZ NOT NULL,
    priority_score INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (barcode, city_plate_code, market_key)
);

CREATE INDEX IF NOT EXISTS idx_barcode_scan_signals_barcode_city_date
ON barcode_scan_signals(barcode, city_plate_code, signal_date);

CREATE INDEX IF NOT EXISTS idx_barcode_scan_events_barcode_city_date
ON barcode_scan_events(barcode, city_plate_code, signal_date);

CREATE INDEX IF NOT EXISTS idx_hot_refresh_candidates_status_due
ON hot_product_refresh_candidates(status, refresh_due_at, priority_score);
"""

_SCHEMA_READY_LOCK = threading.Lock()
_SCHEMA_READY_PATHS: set[str] = set()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _isoformat_utc(_utcnow())


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Optional[str]) -> datetime:
    if value is None or str(value).strip() == "":
        return _utcnow()
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_signal_date(value: Optional[str], scanned_at: datetime) -> str:
    if value is None or str(value).strip() == "":
        return scanned_at.date().isoformat()
    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        parsed = _parse_datetime(text)
        return parsed.date().isoformat()


def _normalize_city_code(value: Any) -> int:
    if value is None or str(value).strip() == "":
        return 0
    try:
        normalized = int(str(value).strip())
    except ValueError as exc:
        raise ValueError("invalid_city_code") from exc
    if normalized < 0 or normalized > 81:
        raise ValueError("invalid_city_code")
    return normalized


def _normalize_scan_count(value: Any) -> int:
    if value is None or str(value).strip() == "":
        return 1
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_scan_count") from exc
    if normalized <= 0:
        raise ValueError("invalid_scan_count")
    return normalized


def _clean_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _event_payload(raw_event: Dict[str, Any]) -> Optional[str]:
    payload: Dict[str, Any] = {}
    for key in ("payload", "metadata", "context"):
        if key in raw_event and raw_event[key] is not None:
            payload[key] = raw_event[key]
    extras = {
        key: value
        for key, value in raw_event.items()
        if key not in RECOGNIZED_EVENT_FIELDS and value is not None
    }
    if extras:
        payload["extra"] = extras
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _stable_event_id(
    barcode: str,
    city_plate_code: int,
    signal_date: str,
    scanned_at: str,
    scan_count: int,
    source_app: str,
    device_id: Optional[str],
    session_id: Optional[str],
    user_id: Optional[str],
    payload_json: Optional[str],
) -> str:
    digest = hashlib.sha256(
        "||".join(
            [
                barcode,
                str(city_plate_code),
                signal_date,
                scanned_at,
                str(scan_count),
                source_app,
                device_id or "",
                session_id or "",
                user_id or "",
                payload_json or "",
            ]
        ).encode("utf-8")
    ).hexdigest()
    return digest[:32]


def _normalize_event(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    barcode = normalize_barcode(raw_event.get("barcode"))
    if barcode is None:
        raise ValueError("invalid_barcode")
    scanned_at = _parse_datetime(raw_event.get("scanned_at"))
    scanned_at_iso = _isoformat_utc(scanned_at)
    signal_date = _normalize_signal_date(raw_event.get("signal_date"), scanned_at)
    city_plate_code = _normalize_city_code(raw_event.get("city_code", raw_event.get("city_plate_code")))
    scan_count = _normalize_scan_count(raw_event.get("scan_count"))
    source_app = _clean_optional_text(raw_event.get("source_app")) or DEFAULT_SOURCE_APP
    device_id = _clean_optional_text(raw_event.get("device_id"))
    session_id = _clean_optional_text(raw_event.get("session_id"))
    user_id = _clean_optional_text(raw_event.get("user_id"))
    payload_json = _event_payload(raw_event)
    event_id = _clean_optional_text(raw_event.get("event_id")) or _stable_event_id(
        barcode=barcode,
        city_plate_code=city_plate_code,
        signal_date=signal_date,
        scanned_at=scanned_at_iso,
        scan_count=scan_count,
        source_app=source_app,
        device_id=device_id,
        session_id=session_id,
        user_id=user_id,
        payload_json=payload_json,
    )
    return {
        "event_id": event_id,
        "barcode": barcode,
        "city_plate_code": city_plate_code,
        "signal_date": signal_date,
        "scanned_at": scanned_at_iso,
        "scan_count": scan_count,
        "source_app": source_app,
        "device_id": device_id,
        "session_id": session_id,
        "user_id": user_id,
        "payload_json": payload_json,
        "created_at": _utcnow_iso(),
    }


def _coerce_events(payload: Union[Dict[str, Any], Sequence[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], bool]:
    rebuild_hot_refresh = True
    if isinstance(payload, list):
        events = list(payload)
    elif isinstance(payload, dict):
        rebuild_hot_refresh = bool(payload.get("rebuild_hot_refresh", True))
        if isinstance(payload.get("events"), list):
            events = list(payload["events"])
        else:
            events = [payload]
    else:
        raise ValueError("events payload must be a JSON object or list")

    if not events:
        raise ValueError("events payload is empty")
    if len(events) > MAX_BATCH_SIZE:
        raise ValueError("batch_limit_exceeded")
    return events, rebuild_hot_refresh


def ensure_ingest_schema(connection) -> None:
    database_path = _database_path(connection)
    with _SCHEMA_READY_LOCK:
        if database_path in _SCHEMA_READY_PATHS:
            return
        if getattr(connection, "backend", "sqlite") == "postgres":
            connection.executescript(INGEST_SCHEMA_PG_SQL)
        else:
            connection.executescript(INGEST_SCHEMA_SQL)
        _SCHEMA_READY_PATHS.add(database_path)


def _object_exists(connection, name: str, object_type: Optional[str] = None) -> bool:
    sql = "SELECT 1 FROM sqlite_master WHERE name = ?"
    params: List[Any] = [name]
    if object_type:
        sql += " AND type = ?"
        params.append(object_type)
    sql += " LIMIT 1"
    return connection.execute(sql, params).fetchone() is not None


def _database_path(connection) -> str:
    backend = getattr(connection, "backend", "sqlite")
    if backend == "postgres":
        return getattr(connection, "db_url_display", "postgres")
    row = connection.execute("PRAGMA database_list").fetchone()
    if row is None:
        return ":unknown:"
    return row[2] or ":memory:"


def _row_dicts(cursor) -> List[Dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _store_event(connection, event: Dict[str, Any]) -> bool:
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO barcode_scan_events (
            event_id,
            barcode,
            city_plate_code,
            signal_date,
            scanned_at,
            scan_count,
            source_app,
            device_id,
            session_id,
            user_id,
            payload_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_id"],
            event["barcode"],
            event["city_plate_code"],
            event["signal_date"],
            event["scanned_at"],
            event["scan_count"],
            event["source_app"],
            event["device_id"],
            event["session_id"],
            event["user_id"],
            event["payload_json"],
            event["created_at"],
        ),
    )
    if cursor.rowcount <= 0:
        return False

    connection.execute(
        """
        INSERT INTO barcode_scan_signals (
            barcode,
            city_plate_code,
            signal_date,
            scan_count,
            source_app,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(barcode, city_plate_code, signal_date, source_app) DO UPDATE SET
            scan_count = barcode_scan_signals.scan_count + excluded.scan_count,
            updated_at = excluded.updated_at
        """,
        (
            event["barcode"],
            event["city_plate_code"],
            event["signal_date"],
            event["scan_count"],
            event["source_app"],
            event["created_at"],
            event["created_at"],
        ),
    )
    return True


class PostgresMirror:
    def __init__(self) -> None:
        self.dsn = os.getenv("MARKET_GELSIN_POSTGRES_DSN", "").strip()
        self.enabled = bool(self.dsn)
        self.error: Optional[str] = None
        self._psycopg = None
        if not self.enabled:
            return
        try:
            import psycopg  # type: ignore
        except ImportError:
            self.error = "psycopg is not installed"
            return
        self._psycopg = psycopg

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.enabled and self._psycopg is not None,
            "dsn_configured": bool(self.dsn),
            "error": self.error,
        }

    def mirror(self, events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        status = self.status()
        if not status["enabled"]:
            return {**status, "written_count": 0}
        if self._psycopg is None:
            return {**status, "written_count": 0}

        written_count = 0
        with self._psycopg.connect(self.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS barcode_scan_events (
                        event_id TEXT PRIMARY KEY,
                        barcode TEXT NOT NULL,
                        city_plate_code INTEGER NOT NULL DEFAULT 0,
                        signal_date DATE NOT NULL,
                        scanned_at TIMESTAMPTZ NOT NULL,
                        scan_count INTEGER NOT NULL DEFAULT 1,
                        source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
                        device_id TEXT,
                        session_id TEXT,
                        user_id TEXT,
                        payload_json TEXT,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS barcode_scan_signals (
                        signal_id BIGSERIAL PRIMARY KEY,
                        barcode TEXT NOT NULL,
                        city_plate_code INTEGER NOT NULL DEFAULT 0,
                        signal_date DATE NOT NULL,
                        scan_count INTEGER NOT NULL,
                        source_app TEXT NOT NULL DEFAULT 'barkod_analiz',
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        UNIQUE (barcode, city_plate_code, signal_date, source_app)
                    )
                    """
                )
                for event in events:
                    cursor.execute(
                        """
                        INSERT INTO barcode_scan_events (
                            event_id,
                            barcode,
                            city_plate_code,
                            signal_date,
                            scanned_at,
                            scan_count,
                            source_app,
                            device_id,
                            session_id,
                            user_id,
                            payload_json,
                            created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (event_id) DO NOTHING
                        RETURNING event_id
                        """,
                        (
                            event["event_id"],
                            event["barcode"],
                            event["city_plate_code"],
                            event["signal_date"],
                            event["scanned_at"],
                            event["scan_count"],
                            event["source_app"],
                            event["device_id"],
                            event["session_id"],
                            event["user_id"],
                            event["payload_json"],
                            event["created_at"],
                        ),
                    )
                    inserted = cursor.fetchone()
                    if inserted is None:
                        continue
                    cursor.execute(
                        """
                        INSERT INTO barcode_scan_signals (
                            barcode,
                            city_plate_code,
                            signal_date,
                            scan_count,
                            source_app,
                            created_at,
                            updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (barcode, city_plate_code, signal_date, source_app) DO UPDATE SET
                            scan_count = barcode_scan_signals.scan_count + EXCLUDED.scan_count,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            event["barcode"],
                            event["city_plate_code"],
                            event["signal_date"],
                            event["scan_count"],
                            event["source_app"],
                            event["created_at"],
                            event["created_at"],
                        ),
                    )
                    written_count += 1
        return {**status, "written_count": written_count}


class FirebaseMirror:
    def __init__(self) -> None:
        self.credentials_path = os.getenv("MARKET_GELSIN_FIREBASE_CREDENTIALS", "").strip()
        self.project_id = os.getenv("MARKET_GELSIN_FIREBASE_PROJECT_ID", "").strip()
        self.collection = os.getenv("MARKET_GELSIN_FIREBASE_COLLECTION", DEFAULT_FIREBASE_COLLECTION).strip() or DEFAULT_FIREBASE_COLLECTION
        self.enabled = bool(self.credentials_path or self.project_id)
        self.error: Optional[str] = None
        self._firebase_admin = None
        self._firestore = None
        if not self.enabled:
            return
        try:
            import firebase_admin  # type: ignore
            from firebase_admin import credentials, firestore  # type: ignore
        except ImportError:
            self.error = "firebase_admin is not installed"
            return

        self._firebase_admin = firebase_admin
        self._firestore = firestore
        try:
            firebase_admin.get_app()
        except ValueError:
            try:
                options: Dict[str, Any] = {}
                if self.project_id:
                    options["projectId"] = self.project_id
                if self.credentials_path:
                    firebase_admin.initialize_app(credentials.Certificate(self.credentials_path), options=options or None)
                else:
                    firebase_admin.initialize_app(options=options or None)
            except Exception as exc:
                self.error = str(exc)[:500]
                self._firebase_admin = None
                self._firestore = None

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.enabled and self._firestore is not None,
            "project_id": self.project_id or None,
            "collection": self.collection,
            "error": self.error,
        }

    def mirror(self, events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        status = self.status()
        if not status["enabled"]:
            return {**status, "written_count": 0}
        if self._firebase_admin is None or self._firestore is None:
            return {**status, "written_count": 0}

        from google.api_core.exceptions import AlreadyExists

        client = self._firestore.client()
        events_collection = client.collection(self.collection).document("events").collection("items")
        signals_collection = client.collection(self.collection).document("daily_signals").collection("items")
        written_count = 0
        for event in events:
            event_doc = events_collection.document(event["event_id"])
            event_payload = {
                "event_id": event["event_id"],
                "barcode": event["barcode"],
                "city_plate_code": event["city_plate_code"],
                "signal_date": event["signal_date"],
                "scanned_at": event["scanned_at"],
                "scan_count": event["scan_count"],
                "source_app": event["source_app"],
                "device_id": event["device_id"],
                "session_id": event["session_id"],
                "user_id": event["user_id"],
                "payload_json": event["payload_json"],
                "created_at": event["created_at"],
            }
            try:
                event_doc.create(event_payload)
            except AlreadyExists:
                continue
            signal_doc_id = "|".join(
                [
                    event["barcode"],
                    str(event["city_plate_code"]),
                    event["signal_date"],
                    event["source_app"],
                ]
            )
            signals_collection.document(signal_doc_id).set(
                {
                    "barcode": event["barcode"],
                    "city_plate_code": event["city_plate_code"],
                    "signal_date": event["signal_date"],
                    "source_app": event["source_app"],
                    "updated_at": event["created_at"],
                    "scan_count": self._firestore.Increment(event["scan_count"]),
                },
                merge=True,
            )
            written_count += 1
        return {**status, "written_count": written_count}


def _mirror_events(events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    postgres = PostgresMirror()
    firebase = FirebaseMirror()
    try:
        postgres_result = postgres.mirror(events)
    except Exception as exc:
        postgres_result = {**postgres.status(), "written_count": 0, "error": str(exc)[:500]}
    try:
        firebase_result = firebase.mirror(events)
    except Exception as exc:
        firebase_result = {**firebase.status(), "written_count": 0, "error": str(exc)[:500]}
    return {
        "postgres": postgres_result,
        "firebase": firebase_result,
    }


def _rebuild_hot_refresh_candidates(connection):
    from .hot_refresh import rebuild_hot_refresh_candidates

    return rebuild_hot_refresh_candidates(connection)


def backfill_existing_scan_events(
    db_path=DEFAULT_DB_PATH,
    batch_size: int = 500,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    batch_size = max(1, min(int(batch_size), MAX_BATCH_SIZE))
    max_rows = None if limit is None else max(1, int(limit))
    mirrored_count = 0
    firebase_written = 0
    postgres_written = 0
    batches = 0
    last_event_id = None

    while True:
        with connect(db_path) as connection:
            ensure_ingest_schema(connection)
            sql = """
                SELECT
                    event_id,
                    barcode,
                    city_plate_code,
                    signal_date,
                    scanned_at,
                    scan_count,
                    source_app,
                    device_id,
                    session_id,
                    user_id,
                    payload_json,
                    created_at
                FROM barcode_scan_events
            """
            params: List[Any] = []
            where_clauses: List[str] = []
            if last_event_id is not None:
                where_clauses.append("event_id > ?")
                params.append(last_event_id)
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            sql += " ORDER BY event_id LIMIT ?"
            params.append(batch_size if max_rows is None else min(batch_size, max_rows - mirrored_count))
            rows = _row_dicts(connection.execute(sql, params))

        if not rows:
            break

        result = _mirror_events(rows)
        firebase_written += int(result["firebase"].get("written_count", 0) or 0)
        postgres_written += int(result["postgres"].get("written_count", 0) or 0)
        mirrored_count += len(rows)
        batches += 1
        last_event_id = rows[-1]["event_id"]
        if max_rows is not None and mirrored_count >= max_rows:
            break

    return {
        "ok": True,
        "scanned_event_count": mirrored_count,
        "batch_count": batches,
        "mirrors": {
            "firebase": {
                **FirebaseMirror().status(),
                "written_count": firebase_written,
            },
            "postgres": {
                **PostgresMirror().status(),
                "written_count": postgres_written,
            },
        },
    }


def describe_ingest_integrations(db_path=DEFAULT_DB_PATH) -> Dict[str, Any]:
    postgres = PostgresMirror()
    firebase = FirebaseMirror()
    with connect(db_path) as connection:
        ensure_ingest_schema(connection)
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM barcode_scan_events) AS event_count,
                (SELECT COUNT(*) FROM barcode_scan_signals) AS signal_count,
                (SELECT COUNT(*) FROM hot_product_refresh_candidates WHERE status = 'planned') AS planned_candidate_count,
                (SELECT MAX(scanned_at) FROM barcode_scan_events) AS last_scanned_at
            """
        ).fetchone()
    last_scanned_at = counts[3]
    if isinstance(last_scanned_at, datetime):
        last_scanned_at = _isoformat_utc(last_scanned_at)
    elif isinstance(last_scanned_at, date):
        last_scanned_at = datetime.combine(last_scanned_at, datetime.min.time(), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "sqlite": {
            "enabled": True,
            "db_path": str(db_path),
            "event_count": counts[0],
            "signal_count": counts[1],
            "planned_hot_refresh_candidates": counts[2],
            "last_scanned_at": last_scanned_at,
        },
        "auth": {
            "token_required": bool(os.getenv("MARKET_GELSIN_INGEST_TOKEN", "").strip()),
        },
        "mirrors": {
            "postgres": {**postgres.status(), "written_count": 0},
            "firebase": {**firebase.status(), "written_count": 0},
        },
    }


def ingest_barcode_scan_payload(
    payload: Union[Dict[str, Any], Sequence[Dict[str, Any]]],
    db_path=DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    raw_events, rebuild_hot_refresh = _coerce_events(payload)
    normalized_events = [_normalize_event(event) for event in raw_events]

    inserted_events: List[Dict[str, Any]] = []
    accepted_events: List[Dict[str, Any]] = []
    warnings: List[str] = []
    with connect(db_path) as connection:
        ensure_ingest_schema(connection)
        for event in normalized_events:
            inserted = _store_event(connection, event)
            accepted_events.append(
                {
                    "event_id": event["event_id"],
                    "barcode": event["barcode"],
                    "city_code": str(event["city_plate_code"]).zfill(2) if event["city_plate_code"] else None,
                    "signal_date": event["signal_date"],
                    "scan_count": event["scan_count"],
                    "source_app": event["source_app"],
                    "inserted": inserted,
                }
            )
            if inserted:
                inserted_events.append(event)
        connection.commit()
        can_rebuild_hot_refresh = _object_exists(connection, "current_offers", "view")
        hot_refresh_candidates: List[Dict[str, Any]] = []
        if rebuild_hot_refresh and inserted_events and can_rebuild_hot_refresh:
            try:
                hot_refresh_candidates = _rebuild_hot_refresh_candidates(connection)
            except Exception as exc:
                warnings.append(f"hot_refresh_rebuild_skipped: {str(exc)[:200]}")

    mirrors = _mirror_events(inserted_events)
    return {
        "ok": True,
        "received_count": len(normalized_events),
        "ingested_count": len(inserted_events),
        "duplicate_count": len(normalized_events) - len(inserted_events),
        "rebuild_hot_refresh": rebuild_hot_refresh,
        "planned_hot_refresh_candidate_count": len(hot_refresh_candidates),
        "warnings": warnings,
        "events": accepted_events,
        "mirrors": mirrors,
    }
