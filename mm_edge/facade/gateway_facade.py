"""
MM Gateway Façade — skeleton
 
Presents the subset of tb_gateway_service.py's interface that connectors
actually call, so upstream connector files (modbus_connector.py, etc.) can
run completely untouched against MM's own systems instead of ThingsBoard's.
 
Method set and contracts confirmed against thingsboard-gateway tag v3.8.3,
commit 7f7e0bf061bf92c2feb12b5098620f118dce364b — see:
  - modbus_dependency_inventory.md  (who calls what, and why)
  - gateway_service_reference.md    (upstream's real behavior per method)
  - M0_architecture_note.md         (summary + open questions)
 
This is a SKELETON. Each method's real contract (signature, return type,
fast/non-blocking behavior where relevant) is preserved from the inventory.
The actual MM-specific logic — mapping resolution, durable queue, cloud
client — is marked TODO for you to design and build. Don't just fill these
in from memory; revisit the relevant Edge guide section for each TODO
before implementing it, since each one maps to a specific architectural
piece (see comments).
"""

import logging
from enum import Enum

from mm_edge.storage.durable_queue import MMDurableQueue

log = logging.getLogger("mm_edge.facade")

class Status(Enum):
    """
    Mirrors the return type of upstream's send_to_storage.
    TODO: confirm the real Status enum's exact members by locating its
    class definition in tb_gateway_service.py / a shared constants module
    — this is listed as an open question in M0_architecture_note.md.
    Do not assume these three are the complete/correct set.
    """
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    FORBIDDEN_DEVICE = "FORBIDDEN_DEVICE"

class MMGatewayFacade:
    """
    Drop-in replacement for the parts of TBGatewayService that connectors
    (Modbus first, then BACnet/MQTT) depend on.
 
    A connector is handed an instance of this class at construction time,
    exactly like it's handed the real gateway-service object upstream —
    see modbus_connector.py __init__, self.__gateway = gateway.
    """
    def __init__(self):
        # In-memory device tracking, mirroring upstream's __connected_devices.
        # Keyed by device_name. Shape of each value is up to you — but
        # whatever add_device stores here, get_devices must be able to
        # read back out correctly.
        self.__connected_devices = {}
        self.stopped = False # read by TBRemoteLoggerHandler's background thread
        self.tb_client = None # checked before the handler tries to send anything - handles None gracefully(sleeps, retries)
        self.__durable_queue = MMDurableQueue(db_path="mm_edge/storage/mm_edge_buffer.db")

        # TODO: wire in MM's own components once they exist, e.g.:
        #   self.__mapping_resolver = ...   # Section 8 — Mapping & Normalizer
        #   self.__durable_queue = ...      # Section 9 — local buffer/replay
        #   self.__mm_cloud_client = ...    # Section 10 — MMCloudClient
 
    def get_config_path(self):
        return "thingsboard_gateway/config/" # need to replace with MM's own config dir to resolve to
    
    # ------------------------------------------------------------------
    # Device lifecycle
    # ------------------------------------------------------------------

    def add_device(self, device_name, content, device_type=None):
        """
        Real upstream behavior (tb_gateway_service.py:1916): stores the
        device in-memory + persists to disk, calls tb_client.gw_connect_device()
        to notify ThingsBoard, records connector metadata as attributes.
 
        Confirmed return type: bool.
 
        This is the natural hook point for MM Mapping resolution — raw
        device_name/device_type needs to become tenant_id/site_id/asset_id/
        meter_id before anything downstream (send_to_storage) can use the
        data meaningfully. See Edge guide Section 8.
        """
        log.info(f"[FACADE] add_device called: {device_name}, type={device_type}")

        if device_name in self.__connected_devices:
            return True  # already known — mirrors upstream's early-return path

        # TODO: resolve device_name/device_type via MM Mapping layer here.
        # If mapping resolution fails (unmapped point), decide: reject the
        # device, or accept it in an explicit "unmapped" state per Section 8's
        # mapping-field table (asset_id "nullable only for explicitly unmapped
        # commissioning data").

        self.__connected_devices[device_name] = {
            "content": content,
            "device_type": device_type,
            # TODO: store resolved mapping context here once the above
            # TODO is implemented (tenant_id, site_id, asset_id, meter_id).
        }

        # TODO: notify whatever MM considers "a device now exists" —
        # this is the MM-equivalent of gw_connect_device.

        return True

    def del_device(self, device_name, remove_device=True):
        """
        Real upstream behavior (tb_gateway_service.py:2024): removes device
        from in-memory tracking, calls tb_client.gw_disconnect_device(),
        persists the change.
 
        Confirmed return type: None (upstream has no explicit return).
        """
        self.__connected_devices.pop(device_name, None)

        # TODO: notify MM's cloud/mapping layer the device disconnected,
        # if that's meaningful in MM's model (open question — see
        # M0_architecture_note.md §6).
 
        return None

    def get_devices(self, connector_id=None):
        """
        Real upstream behavior (tb_gateway_service.py:2045):
          - connector_id=None → full dict of all connected devices
          - connector_id=<id> → filtered dict, reshaped to {name: device_type}
 
        Confirmed: Modbus only ever calls this with NO argument, used for
        membership checks (`if device_name in gateway.get_devices()`).
        TODO: verify whether BACnet/MQTT call this WITH connector_id when
        those connectors are inventoried — if so, implement the filtered
        shape below properly instead of leaving it partial.
        """
        if connector_id is None:
            return self.__connected_devices
 
        # TODO: filter self.__connected_devices by connector_id and reshape
        # to {name: device_type}, matching upstream's shape exactly, once
        # confirmed necessary.
        raise NotImplementedError(
            "get_devices(connector_id=...) shape not yet confirmed as needed — "
            "see open questions in M0_architecture_note.md"
        )

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def send_to_storage(self, connector_name, connector_id, data):
        """
        Real upstream behavior (tb_gateway_service.py:1144): validates,
        then drops data onto an internal queue and returns immediately.
        Actual batching/sending to the platform happens in a SEPARATE
        background loop — NOT inline in this method.
 
        Confirmed return type: Status enum.
 
        CRITICAL CONTRACT: this method is called from the connector's tight
        per-reading loop (see modbus_connector.py __save_data). It MUST
        stay fast and non-blocking — never do a network call inline here.
        Accept the data quickly (e.g. push to MM's own durable queue),
        and let something else (a separate async worker) handle the slow
        work of actually getting it to the MM cloud. See Edge guide
        Section 9 (Local Persistence, Offline Replay and Idempotency).

        some connectors (confirmed: OPC-UA) never call add_device()
        explicitly before sending data — they rely on send_to_storage alone
        to make a device "exist." This method must handle first-time
        registration itself for any previously-unseen device_name.
        """
        log.info(f"send_to_storage called: connector={connector_name}, data={data}")
        
        if connector_name is None or data is None:
            return Status.FAILURE

        device_name = getattr(data, "device_name", None)
        device_type = getattr(data, "device_type", None)

        if device_name is not None and device_name not in self.__connected_devices:
            # Implicit registration path. Reuses add_device's own logic
            # (including its idempotency guard) rather than duplicating it here.
            self.add_device(device_name, {"connector_name": connector_name}, device_type=device_type)

        self.__durable_queue.put(connector_name, connector_id, data)
        #
        # A separate background task/thread should drain that queue and
        # handle the real send + retry/backoff — mirroring your own
        # prototype's enqueue() / drain_loop() split.
 
        return Status.SUCCESS

    # ------------------------------------------------------------------
    # RPC / downlink — safe no-op for V1 (Edge guide Section 5: RPC to
    # devices is DISABLE V1). MM's cloud will never trigger this path
    # since downlink is off, but connectors may still call it defensively.
    # ------------------------------------------------------------------

    def send_rpc_reply(self, device=None, req_id=None, content=None, **kwargs):
        """
        Deliberately inert for V1. Real upstream signature also accepts
        success_sent and wait_for_publish kwargs (tb_gateway_service.py:1793)
        — accepted here via **kwargs so a call never crashes, but ignored.
        """
        return None