from mm_edge.telemetry.models import MMTechnicalReading

class ConvertedDataConverter:
    def convert(self, data) -> list[MMTechnicalReading]:
        readings: list[MMTechnicalReading] = []

        source_id = data.device_name

        for telemetry_entry in data.telemetry:
            measured_at_ms = telemetry_entry.ts

            for datapoint_key, raw_value in telemetry_entry.values.items():
                point_id = datapoint_key.key

                readings.append(
                    MMTechnicalReading(
                        source_id=source_id,
                        point_id=point_id,
                        measured_at_ms=measured_at_ms,
                        raw_value=raw_value,
                    )
                )

        return readings