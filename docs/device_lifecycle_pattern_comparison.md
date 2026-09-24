# Device Lifecycle Pattern Comparison — All 4 Connectors

Source: thingsboard-gateway @ 7f7e0bf061bf92c2feb12b5098620f118dce364b (tag v3.8.3)

| Connector | add_device? | del_device? | get_devices()? | Registration trigger |
|-----------|-------------|-------------|-----------------|----------------------|
| Modbus | Yes, explicit, checked via get_devices() first | Yes, on disconnect | Yes (membership check) | Static config (fixed "slaves" list) |
| OPC-UA | Never called | Only on full connector shutdown | No | Implicit — device "exists" once send_to_storage is called with its name |
| BACnet | Yes, explicit, once per discovered device | Never called | No | Network discovery (Who-Is/I-Am broadcast) |
| MQTT | Yes, explicit, message-triggered | Yes, message-triggered | Yes (same shape as Modbus) | Message content (configured connect/disconnect topics) |

## Façade implications (consolidated)

1. **Explicit registration is the majority pattern** (3 of 4 — Modbus, BACnet, MQTT) but not universal. send_to_storage's implicit- registration fallback (built for OPC-UA) must stay in place unconditionally — it's a safe no-op for connectors that already registered explicitly, since add_device's own idempotency guard (`if device_name in self.__connected_devices: return True`) handles that.

2. **get_devices()'s connector_id-filtered shape is confirmed unused** across all 4 connectors — façade does not need to implement it correctly for V1 (still stubbed as NotImplementedError, deliberately, in gateway_facade.py).

3. **del_device is inconsistently called** (Modbus + MQTT: yes: BACnet: never; OPC-UA: only at shutdown) — no connector-side behavior in the façade should assume del_device is a reliable signal that a device is truly gone.

4. **Three distinct registration TRIGGERS** exist across connectors (static config / network discovery / message content) — the façade itself doesn't care which triggered the call, but this is useful context for understanding why certain connectors behave differently at startup vs. runtime.