from datetime import datetime, timezone
from uuid import uuid4

from mm_edge.identity.gateway_identity import GatewayIdentity
from mm_edge.telemetry.models import (
    MMTechnicalReading,
    MMTelemetryEnvelope,
    MMTelemetryReading,
)

class MMTelemetryEnvelopeFactory:
    SCHEMA_VERSION = 1

    def __init__(self, gateway_dentity: GatewayIdentity):
        self._gateway_identity = gateway_dentity

    def create(self, readings: list[MMTechnicalReading],) -> MMTelemetryEnvelope:
        sent_at = self._utc_now_iso()

        cloud_readings = [
            self._create_reading(reading)
            for reading in readings
        ]

        return MMTelemetryEnvelope(
            schema_version=self.SCHEMA_VERSION,
            organization_id=self._gateway_identity.organization_id,
            site_id=self._gateway_identity.site_id,
            gateway_id=self._gateway_identity.gateway_id,
            sent_at=sent_at,
            readings=cloud_readings,
        )

    def _create_reading(self, reading: MMTechnicalReading) -> MMTelemetryReading:
        return MMTelemetryReading(
            reading_id=str(uuid4()),
            source_id=reading.source_id,
            point_id=reading.point_id,
            measured_at=self._unix_ms_to_iso(reading.measured_at_ms),
            value=reading.raw_value
        )

    @staticmethod
    def _unix_ms_to_iso(timestamp_ms: int) -> str:
        timestamp_seconds = timestamp_ms / 1000

        return (
            datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc,)
                .isoformat()
                .replace("+00:00", "Z")
        )

    @staticmethod
    def _utc_now_iso() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )