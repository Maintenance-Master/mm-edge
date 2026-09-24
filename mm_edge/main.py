import os
os.environ["TB_GW_LOGS_PATH"] = "logs"

import json, time, logging.config
from pathlib import Path

from thingsboard_gateway.connectors.modbus.modbus_connector import AsyncModbusConnector
from mm_edge.facade.gateway_facade import MMGatewayFacade

os.makedirs("logs", exist_ok=True) # handers won't create the folder themselves

with open("mm_edge/config/logging.json") as f:
    logging.config.dictConfig(json.load(f))

log = logging.getLogger("mm_edge.main")
log.info("mm_edge started")

with open("mm_edge/config/modbus.json") as f:
    modbus_config = json.load(f)

facade = MMGatewayFacade()

connector = AsyncModbusConnector(facade, modbus_config, "modbus")
connector.name = "Modbus Connector"
connector.open()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    connector.close()