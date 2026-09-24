# ConvertedData / TelemetryEntry / DatapointKey / Attributes

Source: thingsboard-gateway @ 7f7e0bf061bf92c2feb12b5098620f118dce364b (tag v3.8.3)
Files: thingsboard_gateway/gateway/entities/{converted_data,telemetry_entry,datapoint_key,attributes}.py

Shared data-transfer shape used by ALL connectors (Modbus, BACnet, MQTT, etc.) to hand data to send_to_storage — this is the payload our façade receives.

## ConvertedData
- device_name, device_type: str
- telemetry: List[TelemetryEntry] — time-series readings
- attributes: Attributes — non-timeseries device metadata/state
- metadata: dict
- .to_dict() → plain dict with string keys, e.g.:
    {"deviceName": ..., "deviceType": ..., "telemetry": [...], "attributes": {...}}
  IMPORTANT for our façade: .to_dict() is the natural point to convert into something JSON-serializable for MM's durable queue — DatapointKey objects aren't directly JSON-serializable, but .to_dict() strips them down to plain string keys automatically.

## TelemetryEntry
- ts: int (epoch milliseconds)
- values: Dict[DatapointKey, Any] — one entry per point read at this timestamp

## DatapointKey
- key: str — the actual point/tag name (e.g. "tank_level_cm")
- report_strategy: optional per-point override of when/how often to report
- Used as a dict KEY (not a plain string) so a point can carry extra
  metadata (report_strategy) while still being hashable/comparable —
  see __hash__/__eq__ overrides in the source, both based on (key, report_strategy)

## Attributes
- Same Dict[DatapointKey, Any] shape as telemetry values, but semantically
  different: attributes are point-in-time device state/metadata, not a
  time-series. No timestamp per entry (unlike TelemetryEntry).

## Façade implication
send_to_storage(connector_name, connector_id, data: ConvertedData) should likely call data.to_dict() as the first step before handing off to MM's durable queue — gives a clean, JSON-friendly structure rather than working with the DatapointKey objects directly.