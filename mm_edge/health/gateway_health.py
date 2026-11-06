from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

@dataclass(frozen=True)
class GatewayHealthSnapshot:
    cloud_connected: bool
    reconnect_count: int
    last_connected_at: str | None
    last_disconnected_at: str | None
    last_publish_at: str | None
    last_published_reading_id: str | None
    storage_backlog: int

class GatewayHealth:
    def __init__(self):
        self._lock = Lock()

        self._cloud_connected = False
        self._reconnect_count = 0

        self._has_connected_before = False

        self._last_connected_at = None
        self._last_disconnected_at = None

        self._last_publish_at = None
        self._last_published_reading_id = None

        self._storage_backlog = 0

    def cloud_connected(self) -> None:
        with self._lock:
            if self._has_connected_before:
                self._reconnect_count += 1

            self._has_connected_before = True
            self._cloud_connected = True
            self._last_connected_at = self._utc_now()

    def cloud_disconnected(self) -> None:
        with self._lock:
            self._cloud_connected = False
            self._last_disconnected_at = self._utc_now()

    def publish_succeeded(self, first_reading_id: str | None) -> None:
        with self._lock:
            self._last_publish_at = self._utc_now()
            self._last_published_reading_id = first_reading_id

    def set_storage_backlog(self, backlog: int) -> None:
        with self._lock:
            self._storage_backlog = backlog

    def snapshot(self) -> GatewayHealthSnapshot:
        with self._lock:
            return GatewayHealthSnapshot(
                cloud_connected=self._cloud_connected,
                reconnect_count=self._reconnect_count,
                last_connected_at=self._last_connected_at,
                last_disconnected_at=self._last_disconnected_at,
                last_publish_at=self._last_publish_at,
                last_published_reading_id=self._last_published_reading_id,
                storage_backlog=self._storage_backlog
            )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")