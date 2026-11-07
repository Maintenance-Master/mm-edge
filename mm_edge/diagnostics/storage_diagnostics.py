import logging
import threading

from mm_edge.health.gateway_health import GatewayHealth

from thingsboard_gateway.storage.event_storage import EventStorage

log = logging.getLogger("mm_edge.storage_diagnostics")

class StorageDiagnostics:
    def __init__(
        self,
        event_storage: EventStorage,
        health: GatewayHealth,
        interval_seconds: int = 10
    ):
        self._event_storage = event_storage
        self._interval_seconds = interval_seconds
        self._health = health

        self._stop_event = threading.Event()

        self._thread = threading.Thread(
            target=self._run,
            name="mm-storage-diagnostics",
            daemon=True,
        )

    def start(self) -> None:
        backlog = self._safe_get_backlog()

        log.info("Storage diagnostics started: backlog=%s", backlog)

        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_seconds):
            self._safe_get_backlog()

    def _safe_get_backlog(self):
        try:
            backlog = self._event_storage.len()

            self._health.set_storage_backlog(backlog)

            snapshot = self._health.snapshot()

            log.debug(
                "[HEALTH] cloud_connected=%s "
                "reconnects=%d "
                "backlog=%d "
                "last_publish=%s "
                "last_reading_id=%s",
                snapshot.cloud_connected,
                snapshot.reconnect_count,
                snapshot.storage_backlog,
                snapshot.last_publish_at,
                snapshot.last_published_reading_id,
            )

            return backlog

        except Exception:
            log.exception("Failed to read storage backlog.")
            return "unknown"