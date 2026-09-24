# Gateway-Service Method Reference

Source: thingsboard-gateway @ 7f7e0bf061bf92c2feb12b5098620f118dce364b (tag v3.8.3)

File: thingsboard_gateway/gateway/tb_gateway_service.py

Real implementation of every method/attribute any of the four inventoried connectors (Modbus, OPC-UA, BACnet, MQTT) call on the gateway-service object. Referenced by all four *_dependency_inventory.md docs — method contracts live here ONCE, not repeated per connector.

## send_to_storage(connector_name, connector_id, data) — line 1144
Returns: Status enum (SUCCESS / FAILURE / FORBIDDEN_DEVICE )
```python
class Status(Enum):
    FAILURE = 1,           # NOTE: trailing comma → value is actually (1,), a tuple — see Python gotcha below
    NOT_FOUND = 2,          # value is (2,)
    SUCCESS = 3,            # value is (3,)
    NO_NEW_DATA = 4          # value is plain int 4
    FORBIDDEN_DEVICE = 5    # value is plain int 5
```
5 members total — (NOT_FOUND, NO_NEW_DATA were not observed in any connector call site we inventoried). Façade currently only returns SUCCESS/FAILURE/FORBIDDEN_DEVICE — NOT_FOUND and NO_NEW_DATA are real possible return values from upstream's own send_to_storage that our façade doesn't currently produce. Worth deciding whether MM's façade should ever return these too, or whether they're upstream-specific cases that don't apply to MM's storage model.

Real behavior: FAST, NON-BLOCKING. Validates, then drops data onto an internal queue (self.__converted_data_queue), returns immediately. Actual batching/sending to platform happens in a separate background loop (__send_to_storage, ~line 1179), pulling up to 1000 items or waiting max 500ms per batch.

Façade implication: MUST preserve fast/non-blocking behavior. Called from every connector's tight per-reading loop — blocking here stalls device polling. Also now handles first-time implicit device registration (see gateway_facade.py) for connectors (OPC-UA) that never call add_device.

## add_device(device_name, content, device_type=None) — line 1916
Returns: bool 
⚠️ Different return type from send_to_storage/del_device — no shared convention across methods, façade must match each individually.

Real behavior: stores device in-memory (__connected_devices) + persists to disk (__save_persistent_devices), calls tb_client.gw_connect_device(device_name, device_type).get() to notify the platform, records connector metadata as device attributes, optionally queues shared-attribute sync if the connector supports it.

Façade implication: natural hook point for MM Mapping resolution (Edge guide Section 8) — raw device_name/device_type → tenant_id/site_id/ asset_id/meter_id. NOT called by every connector (OPC-UA never calls it) — send_to_storage must be able to trigger the same resolution independently.

## del_device(device_name, remove_device=True) — line 2024
Returns: None (no explicit return statement)
⚠️ Third distinct return-type pattern (Status enum / bool / None).

Real behavior: removes device from in-memory tracking, calls tb_client.gw_disconnect_device() to notify platform, persists the change. NOT called consistently across connectors — BACnet never calls this at all.

## get_devices(connector_id=None) — line 2045
Returns: dict[str, dict] — SHAPE DEPENDS ON THE ARGUMENT:
  - connector_id=None → full dict of all connected devices, full info
  - connector_id=<id>  → filtered dict, reshaped to {name: device_type}

CONFIRMED (all 4 connectors inventoried): only the no-argument shape is ever used, purely for membership checks (`if name in gateway.get_devices()`). The connector_id-filtered shape is unused across the entire connector set checked so far — façade does not need to implement it correctly for V1.

## get_report_strategy_service() — line 2042
Returns: report strategy service object, or None 

Real behavior: simple getter, `return self._report_strategy_service`.

Used by: OPC-UA only (so far). Confirmed safe to return None from façade — caller guards with an explicit `is not None` check before use.

## get_config_path() — line 786
Returns: str, `return self._config_dir`

Used by: Modbus's BackwardCompatibilityAdapter for legacy config file resolution. NOT used by OPC-UA's or BACnet's own BackwardCompatibilityAdapter implementations — each connector's adapter is independently implemented, not shared, so don't assume this is universally required.

## send_rpc_reply(device=None, req_id=None, content=None, success_sent=None, wait_for_publish=None, ...) — line 1793
Downlink/RPC. Called by all 4 connectors (Modbus 7 sites, OPC-UA 10, BACnet 10, MQTT 2+ related helpers). Since MM V1 disables downlink/RPC entirely, this code path is never genuinely triggered by MM cloud — façade needs only a safe no-op.

## send_attributes(attributes: dict) — line 2242
Used by: MQTT connector only, via `_send_current_converter_config`, which is itself never called anywhere in that file — likely dead code or reflection-invoked elsewhere. Low priority for façade V1.

## is_rpc_in_progress(topic) / rpc_with_reply_processing(topic, content) / register_rpc_request_timeout(...)
Used by: MQTT connector only (its own RPC dispatch/timeout/reply-matching helpers, since MQTT has no built-in request/reply semantics the way other protocols might). Definitions not yet located in tb_gateway_service.py — inferred from call sites only. Downlink/RPC category — safe to leave unimplemented for V1, same as send_rpc_reply.

## tb_client (attribute, not a method)
Two distinct access patterns found:
  - SAFE: logging infrastructure (tb_handler.py) always None-guards before use (`if tb_client is None: sleep(1); continue`).
  - UNSAFE: MQTT connector (lines 778, 782) accesses `gateway.tb_client.client.gw_request_client_attributes(...)` / `gw_request_shared_attributes(...)` with NO None-guard — only reached if MQTT's optional attributeRequests feature is configured and used.
Façade currently sets `self.tb_client = None` — safe for every confirmed path except the unsafe MQTT one above, which stays dormant unless that optional feature is ever needed.

## stopped (attribute, not a method)
Implicit — not called directly by any connector. Required by TBRemoteLoggerHandler (tb_utility/tb_logger.py), read in a background thread's loop condition. This handler is created UNCONDITIONALLY whenever ANY connector logger initializes (via init_logger()), regardless of the enableRemoteLogging config setting. Façade sets `self.stopped = False`.

## TBGatewayService (the class itself)
Imported by OPC-UA (quoted string type hint: `gateway: 'TBGatewayService'`) and BACnet (guarded by `if TYPE_CHECKING:` block, which never executes at runtime). CONFIRMED in both cases: no isinstance() check anywhere — purely documentation/IDE support. Façade does NOT need to inherit from or resemble this class structurally.