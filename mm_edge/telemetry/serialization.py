import json

from mm_edge.telemetry.models import MMTelemetryEnvelope

class MMTelemetrySerializer:
    def serialize(self, envelope: MMTelemetryEnvelope) -> str:
        payload = {
            "schemaVersion": envelope.schema_version,
            "organizationId": envelope.organization_id,
            "siteId": envelope.site_id,
            "gatewayId": envelope.gateway_id,
            "sentAt": envelope.sent_at,
            "readings":[
                {
                    "readingId": reading.reading_id,
                    "sourceId": reading.source_id,
                    "pointId": reading.point_id,
                    "measuredAt": reading.measured_at,
                    "value": reading.value,
                }
                for reading in envelope.readings
            ]
        }

        return json.dumps(payload, separators=(",", ":"))