# MQTT Connector — Gateway Dependency Inventory

Source: thingsboard-gateway @ 7f7e0bf061bf92c2feb12b5098620f118dce364b (tag v3.8.3)

File: thingsboard_gateway/connectors/mqtt/mqtt_connector.py

See: gateway_service_reference.md for full method contracts referenced below.

## Data addressing model
Dynamic, expression-driven device identity (genuinely different from all three other connectors) — device name extracted at runtime from either the message payload (`deviceNameExpressionSource: "message"`, e.g. `${serialNumber}`) or the topic string itself (regex against the topic path). Makes sense given MQTT's nature: many independent devices publish to a shared broker with no pre-negotiated connector-level knowledge of what exists ahead of time. Multiple converter types coexist per connector instance (json / bytes / custom), each with its own topicFilter mapping.

## Gateway-service references

| Line(s) | Call | Category | Notes |
|---------|------|----------|-------|
| 551 | `self.__gateway.send_to_storage(...)` | Telemetry | |
| 689, 965 | `self.__gateway.is_rpc_in_progress(topic)` | Downlink/RPC | MQTT has no built-in RPC semantics, so the gateway provides this bookkeeping |
| 692 | `self.__gateway.rpc_with_reply_processing(topic, content)` | Downlink/RPC | MQTT has no built-in RPC semantics, so the gateway provides this bookkeeping |
| 716 | `self.__gateway.add_device(device_name, {"connector": self}, device_type=...)` | Device lifecycle | Triggered by message content (connect-request topic) |
| 734 | `self.__gateway.get_devices()` | Device lifecycle | Membership check — same no-argument shape as Modbus |
| 736 | `self.__gateway.del_device(...)` | Device lifecycle | Triggered by message content (disconnect-request topic) |
| 778 | `self.__gateway.tb_client.client.gw_request_client_attributes(...)` | Attribute request | ⚠️ See limitation below |
| 782 | `self.__gateway.tb_client.client.gw_request_shared_attributes(...)` | Attribute request | ⚠️ See limitation below |
| 959, 965 | `self.__gateway.register_rpc_request_timeout(...)` | Downlink/RPC | MQTT has no built-in RPC semantics, so the gateway provides this bookkeeping |
| 1006, 1015 | `self.__gateway.send_rpc_reply(...)` | Downlink/RPC | Same category as other connectors |
| 1093 | `self.__gateway.send_attributes({name: config})` | Config/diagnostic | Called from `_send_current_converter_config`, which itself is never invoked anywhere in this file — likely dead code, low priority |

## Device lifecycle pattern
**Explicit, message-driven**: add_device/del_device triggered by a device publishing to a configured connect/disconnect topic (`requestsMapping` in config) — a third distinct triggering mechanism alongside Modbus's static config and BACnet's network discovery. get_devices() used identically to Modbus (no-argument membership check). See device_lifecycle_pattern_comparison.md.

## Real limitation (harder than a simple no-op)
`gateway.tb_client.client.gw_request_client_attributes(...)` / `gw_request_shared_attributes(...)` (lines 778, 782) — **no None-guard** before access, unlike every other tb_client touchpoint found so far (logging infrastructure always None-checks first). Only executes if a device sends a message matching a configured `attributeRequests` mapping entry — an optional MQTT feature. If MM doesn't support this feature, leaving `self.tb_client = None` keeps this path dormant/unused safely. If it's ever needed: `tb_client` can no longer just be None — it would need a real object with a `.client` attribute exposing these two methods.

## is_rpc_in_progress(topic) — line 1770
## rpc_with_reply_processing(topic, content) — line 1773
## register_rpc_request_timeout(content, timeout, topic, cancel_method) — line 1846

Confirmed real signatures (previously inferred from MQTT connector usage only). All three: downlink/RPC category, part of MQTT's own request/reply matching mechanism (MQTT has no built-in RPC semantics, so the gateway provides this bookkeeping). Safe to leave unimplemented in façade for V1 — RPC disabled entirely, same as send_rpc_reply.