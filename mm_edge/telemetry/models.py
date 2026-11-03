from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class MMTechnicalReading:
    source_id: str
    point_id: str
    measured_at_ms: int
    raw_value: Any

@dataclass(frozen=True)
class MMTelemetryReading:
    reading_id: str
    source_id: str
    point_id: str
    measured_at: str
    value: Any

@dataclass(frozen=True)
class MMTelemetryEnvelope:
    schema_version: int

    organization_id: str
    site_id: str
    gateway_id: str

    sent_at: str

    readings: list[MMTelemetryReading]