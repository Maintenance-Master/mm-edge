import logging
import threading
from queue import Empty

from mm_edge.pipeline.incoming_queue import IncomingTelemetryQueue
from mm_edge.telemetry.converted_data_converter import ConvertedDataConverter
from mm_edge.telemetry.envelope_factory import MMTelemetryEnvelopeFactory
from mm_edge.telemetry.serialization import MMTelemetrySerializer

from thingsboard_gateway.storage.event_storage import EventStorage

log = logging.getLogger("mm_edge_telemetry_worker")

class TelemetryWorker:
    def __init__(
            self, 
            incoming_queue: IncomingTelemetryQueue, 
            converter: ConvertedDataConverter,
            envelope_factory: MMTelemetryEnvelopeFactory,
            serializer: MMTelemetrySerializer,
            event_storage: EventStorage
        ):
        self._incoming_queue = incoming_queue
        self._converter = converter
        self._envelope_factory = envelope_factory
        self._serializer = serializer
        self._event_storage = event_storage

        self._stop_event = threading.Event()

        self._thread = threading.Thread(
            target=self._run,
            name="mm-telemetry-worker",
            daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                connector_name, connector_id, data = (
                    self._incoming_queue.get(timeout=0.5)
                )

            except Empty:
                continue

            try:
                technical_readings = self._converter.convert(data)

                if not technical_readings:
                    continue

                envelope = self._envelope_factory.create(technical_readings)

                payload = self._serializer.serialize(envelope)

                log.debug(
                    "[MM ENVELOPE] %s",
                    payload,
                )

                stored = self._event_storage.put(payload)

                if stored:
                    log.debug(
                        "Telemetry envelope accepted by storage: "
                        "connector=%s readings=%d",
                        connector_name,
                        len(envelope.readings),
                    )
                else:
                    log.error(
                        "Telemetry envelope rejected by storage: "
                        "connector=%s readings=%d",
                        connector_name,
                        len(envelope.readings),
                    )

            except Exception:
                log.exception("Failed to process telemetry from connector=%s", connector_name)

            finally:
                self._incoming_queue.task_done()