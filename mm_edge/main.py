import os

os.environ["TB_GW_LOGS_PATH"] = "logs"

import json
import time
import logging.config

from threading import Event

from thingsboard_gateway.connectors.modbus.modbus_connector import (
    AsyncModbusConnector,
)

from mm_edge.facade.gateway_facade import MMGatewayFacade
from mm_edge.pipeline.incoming_queue import IncomingTelemetryQueue
from mm_edge.pipeline.telemetry_worker import TelemetryWorker
from mm_edge.telemetry.converted_data_converter import ConvertedDataConverter
from mm_edge.identity.gateway_identity import GatewayIdentity
from mm_edge.telemetry.envelope_factory import MMTelemetryEnvelopeFactory
from mm_edge.telemetry.serialization import MMTelemetrySerializer
from mm_edge.diagnostics.storage_diagnostics import StorageDiagnostics
from mm_edge.storage.event_storage_factory import create_event_storage

os.makedirs("logs", exist_ok=True) # handers won't create the folder themselves

with open("mm_edge/config/logging.json") as f:
    logging.config.dictConfig(json.load(f))

log = logging.getLogger("mm_edge.main")
log.info("mm_edge started")

with open("mm_edge/config/mm_gateway.json") as f:
    gateway_config = json.load(f)

gateway_identity = GatewayIdentity(
    organization_id=gateway_config["organizationId"],
    site_id=gateway_config["siteId"],
    gateway_id=gateway_config["gatewayId"],
)

with open("mm_edge/config/modbus.json") as f:
    modbus_config = json.load(f)

main_stop_event = Event()

event_storage = create_event_storage(
    config=gateway_config["storage"],
    main_stop_event=main_stop_event
)

diagnostics_config = gateway_config.get("diagnostics", {})

storage_diagnostics = StorageDiagnostics(
    event_storage=event_storage,
    interval_seconds=diagnostics_config.get(
        "storage_log_interval_seconds",
        10,
    )
)

incoming_queue = IncomingTelemetryQueue()

converter = ConvertedDataConverter()

envelope_factory = MMTelemetryEnvelopeFactory(gateway_dentity=gateway_identity)

serializer = MMTelemetrySerializer()

telemetry_worker = TelemetryWorker(
    incoming_queue=incoming_queue, 
    converter=converter,
    envelope_factory=envelope_factory,
    serializer=serializer,
    event_storage=event_storage
)

facade = MMGatewayFacade(incoming_queue=incoming_queue)

connector = AsyncModbusConnector(facade, modbus_config, "modbus")

connector.name = "Modbus Connector"

storage_diagnostics.start()
telemetry_worker.start()
connector.open()

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    log.info("Keyboard interruption")

finally:
    log.info("Stopping mm_edge...")

    connector.close()

    telemetry_worker.stop()

    storage_diagnostics.stop()

    main_stop_event.set()
    event_storage.stop()

    log.info("mm_edge stopped")