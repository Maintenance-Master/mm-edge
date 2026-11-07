import json
import logging
import threading

from datetime import datetime, timezone

from mm_edge.cloud.mqtt_cloud_client import MqttCloudClient
from mm_edge.health.gateway_health import GatewayHealth
from mm_edge.identity.gateway_identity import GatewayIdentity

log = logging.getLogger("mm_edge.heartbeat_worker")

class HeartbeatWorker:
    def __init__(
        self,
        cloud_client: MqttCloudClient,
        health: GatewayHealth,
        gateway_identity: GatewayIdentity,
        interval_seconds: int = 10,
    ):
        if interval_seconds <= 0:
            raise ValueError("Heartbeat interval must be positive")

        self._cloud_client = cloud_client
        self._health = health
        self._gateway_identity = gateway_identity
        self._interval_seconds = interval_seconds

        self._stop_event = threading.Event()

        self._thread = threading.Thread(
            target=self._run,
            name="mm-heartbeat-worker",
            daemon=True,
        )

    def start(self) -> None:
        log.info("Heartbeat worker starting: interval=%ss", self._interval_seconds)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=15)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self._cloud_client.is_connected:
                self._stop_event.wait(1)
                continue

            try:
                payload = self._build_payload()

                if self._cloud_client.publish_heartbeat(payload):
                    log.debug("Heartbeat published successfully")
                else:
                    log.warning("Heartbeat publish failed")

            except Exception:
                log.exception("Unexpected heartbeat error")

            self._stop_event.wait(self._interval_seconds)

    def _build_payload(self) -> str:
        snapshot = self._health.snapshot()

        heartbeat = {
            "schemaVersion": 1,
            "organizationId": self._gateway_identity.organization_id,
            "siteId": self._gateway_identity.site_id,
            "gatewayId": self._gateway_identity.gateway_id,
            "timestamp": self._utc_now_iso(),
            "cloud": {
                "connected": snapshot.cloud_connected,
                "reconnectCount": snapshot.reconnect_count,
                "lastPublishAt": snapshot.last_publish_at,
            },
            "buffer":{
                "records": snapshot.storage_backlog,
            },
        }

        return json.dumps(heartbeat, separators=(",", ":"))

    @staticmethod
    def _utc_now_iso() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )