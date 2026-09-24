# OPC-UA Connector — Gateway Dependency Inventory

Source: thingsboard-gateway @ 7f7e0bf061bf92c2feb12b5098620f118dce364b (tag v3.8.3)

Files: thingsboard_gateway/connectors/opcua/opcua_connector.py
       (+ device.py, backward_compatibility_adapter.py — confirmed zero
       gateway calls in either)

See: gateway_service_reference.md for full method contracts referenced below.

## Data addressing model
Node-based, self-describing address space (vs. Modbus's flat, meaningless addresses). Two addressing styles (thingsboard_gateway/config/opcua.json):
  - "path": human-readable browse path, e.g. "Root.Objects.Device1.Humidity"
  - NodeId literal: "${ns=2;i=5}" (ns=namespace index, i=numeric identifier; string/GUID identifier variants also exist)
A "device" is itself a node in the server's tree (deviceNodePattern), discoverable via periodic re-scanning (scanPeriodInMillis) rather than a fixed config-only entry like Modbus's "slaves" array.

## Gateway-service references

| Line(s) | Call | Category | Notes |
|---------|------|----------|-------|
| 99 | `self.__gateway: 'TBGatewayService' = gateway` | Setup | Quoted type hint only — confirmed NOT isinstance-checked, harmless |
| 116, 118, 1050, 1065 | `gateway.get_report_strategy_service()` | Config | NEW vs Modbus — safe to return None, caller guards with `is not None` |
| 474 | `self.__gateway.del_device(...)` | Device lifecycle | Called ONLY during connector shutdown |
| 875 | `self.__gateway.send_to_storage(...)` | Telemetry | SUBSCRIPTION path (server-pushed monitored-item notifications) |
| 1268 | `self.__gateway.send_to_storage(...)` | Telemetry | POLLING path (`__convert_retrieved_data`) — periodic bulk reads |
| 1286 | `self.__gateway.send_to_storage(...)` | Telemetry | Shared statistics-tracking wrapper (`__send_data_to_gateway_storage`) |
| ~1440–1551 | `self.__gateway.send_rpc_reply(...)` (10 sites) | Downlink/RPC | Same category as Modbus — safe no-op for V1 |

## Confirmed absent (unlike Modbus)
- `add_device()` — zero matches, case-insensitive, whole file
- `get_devices()` — zero matches, case-insensitive, whole file

## Device lifecycle pattern
**Implicit only**: no `add_device` call anywhere. `del_device` (line 474) only runs at connector shutdown, iterating the connector's own internally-tracked `self.__device_nodes` (populated by its own `Device` class in device.py — confirmed zero gateway coupling in that file). Device "exists" purely by virtue of `send_to_storage` being called with its name. See device_lifecycle_pattern_comparison.md.

## Why 3 send_to_storage sites (not redundant)
Two genuinely different data-acquisition mechanisms converge on the same call — matches config's simultaneous `"enableSubscriptions": true` + `"pollPeriodInMillis"`. send_to_storage's contract is identical regardless of which path triggers it.

## Façade implications
1. **send_to_storage cannot assume add_device already ran.** If MM Mapping resolution happens in add_device, send_to_storage must trigger that same resolution itself for any previously-unseen device_name. (Implemented — see gateway_facade.py.)
2. **Limitation**: the implicit-registration path in send_to_storage only receives connector_name/connector_id (strings), not the connector object itself — so it cannot capture the `{CONNECTOR_PARAMETER: self}` back-reference explicit add_device calls provide. Fine for V1 (RPC disabled); would need revisiting if downlink/RPC is ever enabled for an implicitly-registering connector.