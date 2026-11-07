import os
import json
import time

import logging
import logging.config

from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

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
from mm_edge.cloud.mqtt_cloud_client import MqttCloudClient
from mm_edge.cloud.cloud_publisher_worker import CloudPublisherWorker
from mm_edge.health.gateway_health import GatewayHealth
from mm_edge.health.heartbeat_worker import HeartbeatWorker

os.environ["TB_GW_LOGS_PATH"] = "logs"

os.makedirs("logs", exist_ok=True) # handers won't create the folder themselves

with open("mm_edge/config/logging.json") as f:
    logging.config.dictConfig(json.load(f))

Path("logs").mkdir(exist_ok=True)

file_handler = TimedRotatingFileHandler(
    filename="logs/mm-edge.log",
    when="midnight",
    backupCount=14,
    encoding="utf-8",
)

file_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
)

logging.getLogger().addHandler(file_handler)

logging.getLogger("pymodbus.logging").setLevel(logging.ERROR)

log = logging.getLogger("mm_edge.main")
log.info("MM Edge started")

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

gateway_health = GatewayHealth()

event_storage = create_event_storage(
    config=gateway_config["storage"],
    main_stop_event=main_stop_event
)

diagnostics_config = gateway_config.get("diagnostics", {})

storage_diagnostics = StorageDiagnostics(
    event_storage=event_storage,
    health=gateway_health,
    interval_seconds=diagnostics_config.get(
        "storage_log_interval_seconds",
        10,
    )
)

cloud_config = gateway_config["cloud"]

cloud_client = MqttCloudClient(
    config=cloud_config,
    gateway_identity=gateway_identity,
    health=gateway_health
)

cloud_publisher = CloudPublisherWorker(
    event_storage=event_storage,
    cloud_client=cloud_client,
    health=gateway_health,
    retry_delay_seconds=cloud_config.get("retryDelaySeconds", 3)
)

heartbeat_worker = HeartbeatWorker(
    cloud_client=cloud_client,
    health=gateway_health,
    gateway_identity=gateway_identity,
    interval_seconds=cloud_config.get("heartbeatIntervalSeconds", 10)
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

cloud_client.start()
cloud_publisher.start()

heartbeat_worker.start()

storage_diagnostics.start()
telemetry_worker.start()

connector.open()

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    log.debug("Keyboard interruption.")

finally:
    log.info("Stopping MM Edge...")

    connector.close()

    telemetry_worker.stop()

    heartbeat_worker.stop()

    cloud_publisher.stop()

    cloud_client.stop()

    storage_diagnostics.stop()

    main_stop_event.set()
    event_storage.stop()

    log.info("MM Edge stopped.")