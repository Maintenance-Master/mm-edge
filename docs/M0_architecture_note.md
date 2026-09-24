# M0 — Upstream Audit & Spike: Architecture Note

**Author:** Gihan Akila
**Date:** 2026/09/21
**Milestone:** M0 (Edge Implementation Guide, Section 19)
**Upstream baseline:** thingsboard-gateway, tag `v3.8.3`, commit `7f7e0bf061bf92c2feb12b5098620f118dce364b`

---

## 1. Scope of this spike

Per the Edge Implementation Guide's M0 scope: pin the upstream release/ commit, run the official gateway end-to-end against a real (simulated) Modbus device, and inventory gateway-service dependencies across all four priority connectors (Modbus, BACnet, MQTT — P0; OPC-UA — P1, Section 7.2). This note also captures architectural findings affecting the design of the MM compatibility façade (Section 6.2) and the working façade skeleton itself (mm_edge/facade/gateway_facade.py).

## 2. Environment

- **ThingsBoard CE**: `thingsboard/tb-postgres:3.8.1`, Docker Compose, Postgres 16. Notable non-default settings for this image variant:
  - Web server listens on **port 9090 internally** (not 8080, as newer `tb-node`-based docs assume) — compose must map `"8080:9090"`.
  - Requires a persistent volume at `/data`, or the install step re-runs and fails with duplicate-key errors on every container recreation.
  - `INSTALL_TB` should be `"true"` only for the first boot against an empty Postgres volume, then flipped to `"false"`.
- **ThingsBoard IoT Gateway**: cloned from the official repo, checked out at tag `3.8.3` (commit above), run from source in a Python 3.11 venv (deliberately not Docker — needed source-level visibility). Run as a module: `python -m thingsboard_gateway.tb_gateway`.
- **Test device**: `simulated_modbus_device.py`, a Modbus TCP server on `localhost:5020`, reused from the earlier
  prototype pipeline.

## 3. End-to-end proof (real gateway)

Confirmed working: simulated Modbus device → unmodified ThingsBoard IoT Gateway → ThingsBoard CE. Gateway auto-created a `tank_01` device entity; telemetry observed updating live, matching the simulator's output.

Config correction made: `pump_status` must use Modbus type `"16int"`, not `"bits"` — `"bits"` unpacks a register into individual bit flags rather than treating the whole register as one integer, which doesn't match how the simulator encodes the value. Small-scale concrete example of exactly the raw-value/semantic gap Section 8 assigns to the future MM Mapping and Normalizer layer.

## 4. Dependency inventory — summary across all 4 connectors

Full detail in modbus_/opcua_/bacnet_/mqtt_dependency_inventory.md. Method contracts consolidated once in gateway_service_reference.md. Cross-connector lifecycle comparison in device_lifecycle_pattern_comparison.md.

Core method set confirmed needed for V1 (read-only) across all connectors: `get_devices`, `add_device`, `del_device`, `send_to_storage` — plus `get_report_strategy_service` and `get_config_path` (used by some connectors, not others) and an implicit logging-infrastructure contract (`.stopped`, `.tb_client`) required regardless of connector type. `send_rpc_reply` (and MQTT's related RPC helpers) confirmed safe as no-ops — RPC/downlink disabled entirely for V1 (Section 5).

Key cross-connector finding: **device registration is NOT uniform.** 3 of 4 connectors register explicitly (add_device before data flows); OPC-UA registers implicitly (device "exists" once send_to_storage sees its name). The façade's send_to_storage was updated to handle this — see Section 6.

## 5. End-to-end proof (façade, not just real gateway)

Built mm_edge/facade/gateway_facade.py and a standalone entry point (mm_edge/main.py) that constructs the REAL, unmodified Modbus connector directly against the façade, bypassing TBGatewayService entirely.

Confirmed via runtime test: add_device() and send_to_storage() both called correctly, with real ConvertedData telemetry (see converted_data_reference.md) flowing from the simulated device through the untouched upstream connector into façade methods.

Two additional façade requirements surfaced only by actually running this (not discoverable by static grep alone):
- `get_config_path()` — used by Modbus's BackwardCompatibilityAdapter
- `.stopped` / `.tb_client` — implicit contract from shared logging infrastructure (triggered by init_logger(), unconditionally, regardless of connector type) — see gateway_service_reference.md for full detail.

Lesson: grepping "self.__gateway." only finds DIRECT calls on the stored reference. It misses (a) calls on the bare constructor parameter before assignment, and (b) transitive requirements imposed by shared utilities the gateway object gets passed into. Both gaps were only found by actually running the connector against the façade and reading the resulting tracebacks.

Also required: running a connector outside TBGatewayService needs manual `logging.basicConfig()` — the real gateway's logs.json-based `logging.config.dictConfig()` setup is skipped entirely when bypassing TBGatewayService, so connector log output silently goes nowhere without it.

## 6. Façade design decisions made so far

- `send_to_storage` implements implicit first-time device registration (calls `self.add_device(...)` internally for any previously-unseen device_name), reusing add_device's own idempotency guard rather than duplicating logic — required for OPC-UA support, safe no-op for the other three connectors.
- Known limitation: the implicit path cannot capture a connector back-reference the way explicit add_device does (send_to_storage only receives connector_name/connector_id as strings) — acceptable for V1 since RPC is disabled.
- Return types deliberately NOT unified across façade methods — each matches its own real upstream contract (Status enum / bool / None) rather than a single convention, since calling code may check specific return values.

## 7. Open questions / carried forward

- Locate and confirm the real `Status` enum class definition — members so far only inferred from usage (SUCCESS/FAILURE/FORBIDDEN_DEVICE).
- Locate real definitions of MQTT-only RPC helpers (`is_rpc_in_progress`, `rpc_with_reply_processing`, `register_rpc_request_timeout`) in tb_gateway_service.py — currently only inferred from connector-side usage.
- Decide whether device persistence-to-disk (mirroring upstream's `__save_persistent_devices`) is needed in MM's façade for V1, or whether MM's own device/mapping registry makes this redundant.
- If MM ever needs to support MQTT's optional `attributeRequests` feature: `self.tb_client` can no longer stay `None` — needs a real object exposing `.client.gw_request_client_attributes` / `.gw_request_shared_attributes`.
- `get_devices(connector_id=...)` filtered-shape: CONFIRMED unused by all 4 connectors — this question is now closed, no façade work needed for V1.
- OPC-UA and BACnet not yet run live against the façade (only Modbus has been runtime-tested) — worth doing at least once each to validate the implicit-registration path (OPC-UA) and the missing-del_device gap (BACnet) in practice, not just via static reading.

## 8. Reproducibility

- Upstream commit: `7f7e0bf061bf92c2feb12b5098620f118dce364b` (tag `v3.8.3`)
- Local repo has `upstream` remote pointing to the official ThingsBoard gateway repo (Section 6.1 fork strategy).
- ThingsBoard CE docker-compose config and gateway config files kept alongside this note for environment reproduction.