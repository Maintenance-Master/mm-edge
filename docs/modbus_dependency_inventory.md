# Modbus Connector — Gateway Dependency Inventory

Source: thingsboard-gateway @ 7f7e0bf061bf92c2feb12b5098620f118dce364b (tag v3.8.3)

File: thingsboard_gateway/connectors/modbus/modbus_connector.py

See: gateway_service_reference.md for full method contracts referenced below.

## Data addressing model
Flat numeric register addresses (function code + address), no inherent meaning — config assigns meaning (e.g. address 0 = tank_level_cm). Type must match how the source device encodes the value (e.g. "bits" ≠ a plain 0/1 integer — confirmed via the pump_status bug in M0_architecture_note.md).

## Gateway-service references

| Line(s)  | Call | Category |
|----------|------|----------|
| 81       | `self.__gateway = gateway` | Setup |
| 329, 333 | `self.__gateway.get_devices()` | Device lifecycle |
| 334      | `self.__gateway.del_device(...)` | Device lifecycle |
| 343      | `self.__gateway.add_device(device_name, {CONNECTOR_PARAMETER: self}, device_type=...)` | Device lifecycle |
| 384      | `self.__gateway.send_to_storage(...)` | Telemetry |
| 566–685  | `self.__gateway.send_rpc_reply(...)` (7 sites) | Downlink/RPC |

## Device lifecycle pattern
**Explicit-first**: `get_devices()` checked for membership → `add_device()`
if new → `del_device()` on disconnect. See
device_lifecycle_pattern_comparison.md for how this compares across all
four connectors.

## Internal pipeline (connector-internal, before any gateway call)
Own Thread + own private asyncio event loop (not shared with gateway's main
loop). 3-stage pipeline via in-memory queues:
`__process_requests` → `__convert_data` → `__save_data`
Gateway calls concentrated in the final (`__save_data`) stage.

## Open question
`add_device` passes `{CONNECTOR_PARAMETER: self}` — connector hands a
reference to itself back to the gateway. Inferred (not confirmed from
source): likely used for routing RPC/downlink commands back to the
originating connector. Low priority to resolve fully since RPC is
disabled for V1.

## Summary
- 4 core methods needed for V1: `get_devices`, `del_device`, `add_device`, `send_to_storage`
- 1 safe-no-op method: `send_rpc_reply` (7 sites, all downlink/RPC — never triggered in V1)