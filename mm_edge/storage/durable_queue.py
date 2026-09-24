import sqlite3, json, threading
from datetime import datetime, timezone

class MMDurableQueue:
    """
    Minimal local buffer for MM Edge, following the same two-phase
    read/acknowledge pattern as upstream's EventStorage interface
    (see gateway_service_reference.md) — but deliberately WITHOUT
    upstream's multi-file rotation complexity. Single SQLite table,
    single file. Revisit only if volume/retention actually demands it.
    """

    def __init__(self, db_path="mm_edge_buffer.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connector_name TEXT NOT NULL,
                connector_id TEXT,
                payload TEXT NOT NULL,       -- JSON: ConvertedData.to_dict()
                created_at TEXT NOT NULL
            )
        """)
        self._conn.commit()
        self._last_read_max_id = None        # high-water mark — mirrors upstream's delete_time_point

    def put(self, connector_name, connector_id, converted_data):
        payload_dict = converted_data.to_dict() if hasattr(converted_data, "to_dict") else converted_data
        payload = json.dumps(payload_dict)
        with self._lock:
            self._conn.execute(
                "INSERT INTO outbox (connector_name, connector_id, payload, created_at) VALUES (?, ?, ?, ?)",
                (connector_name, connector_id, payload, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def get_event_pack(self, batch_size=100):
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, connector_name, connector_id, payload FROM outbox ORDER BY id LIMIT ?",
                (batch_size,),
            ).fetchall()
        if rows:
            self._last_read_max_id = rows[-1][0]   # track position — do NOT delete yet
        return rows

    def event_pack_processing_done(self):
        if self._last_read_max_id is not None:
            with self._lock:
                self._conn.execute("DELETE FROM outbox WHERE id <= ?", (self._last_read_max_id,))
                self._conn.commit()
            self._last_read_max_id = None

    def len(self):
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]