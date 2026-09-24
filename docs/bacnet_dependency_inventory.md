# BACnet Connector — Gateway Dependency Inventory

Source: thingsboard-gateway @ 7f7e0bf061bf92c2feb12b5098620f118dce364b (tag v3.8.3)

Files: thingsboard_gateway/connectors/bacnet/bacnet_connector.py
       (+ device.py, application.py, backward_compatibility_adapter.py,
       ede_parser.py — confirmed zero gateway calls in all four)

See: gateway_service_reference.md for full method contracts referenced below.

## Data addressing model
Three-part addressing, standardized object types (a real protocol-level vocabulary, not config-assigned meaning): objectType (e.g. "analogInput", "binaryValue") + objectId (instance number) + propertyId (usually "presentValue", but objects carry other properties too — units, description, reliability, status flags).

Structural difference from Modbus/OPC-UA: BACnet is peer-to-peer — the gateway must register itself as a BACnet device on the network (its own objectIdentifier/vendorIdentifier, see config's "application" section) and devices are found via broadcast discovery (Who-Is/I-Am, typically UDP port 47808), not dialed directly.

EDE (Engineering Data Exchange) support (ede_parser.py): can bulk-import a vendor-exported point list instead of hand-writing every point in JSON — no gateway coupling, purely a config-population convenience.

Directly relevant to the guide's own Chiller reference use case (Section 17 — BMS BACnet → Leaving Water Temperature) — this is the real mechanism behind that scenario.

## Gateway-service references

| Line(s) | Call | Category | Notes |
|---------|------|----------|-------|
| 60–61 | `if TYPE_CHECKING: from ... import TBGatewayService` | Setup | Import never executes at runtime — confirmed harmless, same conclusion as OPC-UA's quoted type hint, via the more idiomatic mechanism |
| 351 | `self.__gateway.add_device(device_name, {"connector": self}, device_type=...)` | Device lifecycle | Triggered once per discovered device (via `__add_device`, called on Who-Is/I-Am response) |
| 697 | `self.__gateway.send_to_storage(...)` | Telemetry | Single call site — no polling/subscription split like OPC-UA |
| 845–1001 (10 sites) | `self.__gateway.send_rpc_reply(...)` | Downlink/RPC | Same safe-no-op category as before |

## Confirmed absent
- `del_device()` — zero matches. Devices are never explicitly deregistered from the gateway; presumably handled purely as local "disconnected" state inside BACnet's own `Devices` collection (device.py). Not a façade problem, just a real inconsistency across connectors worth knowing about.
- `get_devices()` — zero matches. (Note: `self.__devices.get_devices_by_id` seen in source is a call on BACnet's OWN local `Devices` collection class, not the gateway's method — confirmed by checking device.py.)

## Device lifecycle pattern
**Explicit-first, no cleanup**: add_device called once per device discovered via BACnet's own Who-Is/I-Am network discovery mechanism (distinct trigger from Modbus's static config). No del_device ever called. See device_lifecycle_pattern_comparison.md.

## Other notable finding
`Device` class (device.py) includes `subscription_watchlog` — background health monitoring for BACnet's own subscription mechanism (detects a silently-stalled subscription). Connects to Edge guide Section 15 (Health/Diagnostics) — not gateway-facing, purely internal to the connector, but a useful pattern to be aware of.