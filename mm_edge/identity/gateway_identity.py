from dataclasses import dataclass

@dataclass(frozen=True)
class GatewayIdentity:
    organization_id: str
    site_id: str
    gateway_id: str