import logging
import threading
import json

from thingsboard_gateway.storage.event_storage import EventStorage

from mm_edge.cloud.mqtt_cloud_client import MqttCloudClient
from mm_edge.health.gateway_health import GatewayHealth

log = logging.getLogger("mm_edge.cloud_publisher_worker")

class CloudPublisherWorker:
    def __init__(
        self,
        event_storage: EventStorage,
        cloud_client: MqttCloudClient,
        health: GatewayHealth,
        retry_delay_seconds: float = 3.0,
    ):
        self._event_storage = event_storage
        self._cloud_client = cloud_client
        self._health = health
        self._retry_delay_seconds = retry_delay_seconds

        self._stop_event = threading.Event()

        self._thread = threading.Thread(
            target=self._run,
            name="mm-cloud-publisher",
            daemon=True
        )

    def start(self) -> None:
        log.info("Cloud publisher worker started")

        self._thread.start()


    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=10)

        log.info("Cloud publisher worker stopped")

    def _run(self) -> None:
        while not self._stop_event.is_set():

            if not self._cloud_client.is_connected:
                self._stop_event.wait(self._retry_delay_seconds)
                continue

            try:
                event_pack = self._event_storage.get_event_pack()

                if not event_pack:
                    self._stop_event.wait(0.5)
                    continue

                log.info(
                    "Publishing telemetry pack: "
                    "events=%d backlog=%d",
                    len(event_pack),
                    self._event_storage.len(),
                )

                pack_succeeded = self._publish_pack(event_pack)

                if not pack_succeeded:
                    log.warning(
                        "Telemetry pack was not fully published; "
                        "leaving pack in storage for retry"
                    )

                    self._stop_event.wait(self._retry_delay_seconds)

                    continue

                self._event_storage.event_pack_processing_done()

                log.info(
                    "Telemetry pack acknowledged: "
                    "events=%d remaining=%d",
                    len(event_pack),
                    self._event_storage.len(),
                )

            except Exception:
                log.exception(
                    "Unexpected cloud publishing error; "
                    "pack will remain available for retry"
                )

                self._stop_event.wait(self._retry_delay_seconds)

    def _publish_pack(self, event_pack: list) -> bool:
        for event in event_pack:

            if self._stop_event.is_set():
                return False

            if not self._cloud_client.is_connected:
                return False

            published = self._cloud_client.publish_telemetry(event)

            if not published:
                return False
            
            first_reading_id, reading_count = self._get_event_summary(event)

            self._health.publish_succeeded(first_reading_id)

            log.info(
                "Telemetry event published: "
                "first_reading_id=%s readings=%d",
                first_reading_id,
                reading_count,
            )

        return True

    def _get_event_summary(self, event: str) -> tuple[str | None, int]:
        try:
            payload = json.loads(event)

            readings = payload.get("readings", [])

            if not readings:
                return None, 0

            return readings[0].get("readingId"), len(readings)

        except Exception:
            return None, 0