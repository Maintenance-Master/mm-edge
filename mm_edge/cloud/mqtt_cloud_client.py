import logging
import os
import ssl
import threading

from uuid import UUID

import paho.mqtt.client as mqtt

from mm_edge.identity.gateway_identity import GatewayIdentity
from mm_edge.health.gateway_health import GatewayHealth

log = logging.getLogger("mm_edge.mqtt_cloud_client")

class MqttCloudClient:
    def __init__(self, config: dict, gateway_identity: GatewayIdentity, health: GatewayHealth):
        self._config = config
        self._gateway_identity = gateway_identity
        self._health = health

        self._host = config["host"]
        self._port = int(config.get("port", 8883))
        self._qos = int(config.get("qos", 1))
        self._keep_alive_seconds = int(config.get("keepAliveSeconds", 60))
        self._publish_timeout_seconds = float(config.get("publishTimeoutSeconds", 10))

        gateway_id = UUID(gateway_identity.gateway_id)

        self._client_id = f"gw-{gateway_id.hex}"
        self._username = self._client_id

        password_environment_variable = config.get("passwordEnvironmentVariable", "MM_MQTT_PASSWORD")

        self._password = os.getenv(password_environment_variable)

        if not self._password:
            raise RuntimeError(
                f"MQTT password environment variable "
                f"'{password_environment_variable}' is not set."
            )

        self._topic = self._build_telemetry_topic()

        self._connected = threading.Event()

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311
        )

        self._client.username_pw_set(
            username=self._username,
            password=self._password,
        )

        self._configure_tls()

        self._client.reconnect_delay_set(min_delay=1, max_delay=30)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    def start(self) -> None:
        log.info(
            "Starting MQTT cloud client: "
            "host=%s port=%s client_id=%s",
            self._host,
            self._port,
            self._client_id,
        )

        self._client.connect_async(host=self._host, port=self._port, keepalive=self._keep_alive_seconds)

        self._client.loop_start()

    def stop(self) -> None:
        log.info("Stopping MQTT cloud client")

        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()

        self._connected.clear()

    def publish(self, payload: str) -> bool:
        if not self.is_connected:
            return False

        try:
            result = self._client.publish(
                topic=self._topic,
                payload=payload,
                qos=self._qos,
                retain=False
            )

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                log.warning(
                    "MQTT publish was not accepted locally: rc=%s",
                    result.rc,
                )
                return False

            result.wait_for_publish(timeout=self._publish_timeout_seconds)

            if not result.is_published():
                log.warning("MQTT publish confirmation timed out")
                return False

            return True

        except Exception:
            log.exception("MQTT publish failed")
            return False

    def _configure_tls(self) -> None:
        ca_certificate = self._config["caCertificate"]

        ssl_context = ssl.create_default_context(cafile=ca_certificate)

        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

        self._client.tls_set_context(ssl_context)

    def _build_telemetry_topic(self) -> str:
        organization_id = str(UUID(self._gateway_identity.organization_id))

        site_id = str(UUID(self._gateway_identity.site_id))

        gateway_id = str(UUID(self._gateway_identity.gateway_id))

        return (
            f"mm/v1/tenants/{organization_id}"
            f"/sites/{site_id}"
            f"/gateways/{gateway_id}"
            f"/telemetry"
        )

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties,
    ):
        if reason_code == 0:
            self._connected.set()
            self._health.cloud_connected()

            log.info("Connected to MM MQTT broker: topic=%s", self._topic)

        else:
            self._connected.clear()
            log.error("MQTT connection rejected: reason=%s", reason_code)

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ):
        self._connected.clear()
        self._health.cloud_disconnected()

        log.warning("Disconnected from MM MQTT broker: reason=%s", reason_code)