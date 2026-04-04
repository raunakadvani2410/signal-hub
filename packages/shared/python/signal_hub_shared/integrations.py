"""
Integration registry: static configuration and metadata for all supported integrations.

This is the single source of truth for integration status, connector type, and risk level.
When adding a new integration, add it here and mirror the change in:
  - packages/shared/typescript/src/integrations.ts
  - docs/product-spec.md
  - .claude/rules/integrations.md
"""

from enum import Enum

from pydantic import BaseModel


class IntegrationStatus(str, Enum):
    OFFICIAL = "official"
    OFFICIAL_CONSTRAINED = "official_constrained"
    THIRD_PARTY_EXPERIMENTAL = "third_party_experimental"
    LOCAL_ONLY_EXPERIMENTAL = "local_only_experimental"


class ConnectorType(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    VENDOR_CONNECTOR = "vendor_connector"
    LOCAL_FILE = "local_file"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntegrationConfig(BaseModel):
    integration_key: str
    display_name: str
    status: IntegrationStatus
    connector_type: ConnectorType
    risk_level: RiskLevel
    official_api_available: bool
    notes: str


INTEGRATION_REGISTRY: list[IntegrationConfig] = [
    IntegrationConfig(
        integration_key="gmail",
        display_name="Gmail",
        status=IntegrationStatus.OFFICIAL,
        connector_type=ConnectorType.OAUTH2,
        risk_level=RiskLevel.LOW,
        official_api_available=True,
        notes="Google Gmail REST API v1. OAuth 2.0 with offline access and refresh tokens.",
    ),
    IntegrationConfig(
        integration_key="google_calendar",
        display_name="Google Calendar",
        status=IntegrationStatus.OFFICIAL,
        connector_type=ConnectorType.OAUTH2,
        risk_level=RiskLevel.LOW,
        official_api_available=True,
        notes="Google Calendar API v3. Shares the same Google OAuth app as Gmail.",
    ),
    IntegrationConfig(
        integration_key="notion",
        display_name="Notion",
        status=IntegrationStatus.OFFICIAL,
        connector_type=ConnectorType.OAUTH2,
        risk_level=RiskLevel.LOW,
        official_api_available=True,
        notes="Notion REST API. Supports OAuth or a static internal integration token.",
    ),
    IntegrationConfig(
        integration_key="whatsapp",
        display_name="WhatsApp",
        status=IntegrationStatus.OFFICIAL_CONSTRAINED,
        connector_type=ConnectorType.API_KEY,
        risk_level=RiskLevel.LOW,
        official_api_available=True,
        notes=(
            "Primary path: Meta WhatsApp Business Platform / Cloud API. "
            "Requires a verified Meta Business account and a dedicated WhatsApp Business number — "
            "a personal consumer account cannot be connected via this path. "
            "If the official path does not fit the use case, a vendor connector may be evaluated "
            "as a secondary option with an explicit tradeoff review. "
            "Do not use unofficial libraries (e.g. whatsapp-web.js) — they violate WhatsApp ToS."
        ),
    ),
    IntegrationConfig(
        integration_key="linkedin",
        display_name="LinkedIn",
        status=IntegrationStatus.THIRD_PARTY_EXPERIMENTAL,
        connector_type=ConnectorType.VENDOR_CONNECTOR,
        risk_level=RiskLevel.MEDIUM,
        official_api_available=False,
        notes=(
            "No personal messaging API available from LinkedIn. "
            "The LinkedIn Messaging API requires LinkedIn Partner Program access. "
            "Viable path: a connector vendor (e.g. Unipile) that manages a LinkedIn session. "
            "Do not build a custom scraper or browser automation. "
            "Confirm vendor approach before writing any integration code."
        ),
    ),
    IntegrationConfig(
        integration_key="imessage",
        display_name="iMessage",
        status=IntegrationStatus.LOCAL_ONLY_EXPERIMENTAL,
        connector_type=ConnectorType.LOCAL_FILE,
        risk_level=RiskLevel.LOW,
        official_api_available=False,
        notes=(
            "macOS-only. No public API. Read-only access via local SQLite at "
            "~/Library/Messages/chat.db. Requires macOS Full Disk Access permission. "
            "Schema is undocumented and may break between OS updates. "
            "Must be opt-in and behind the ENABLE_IMESSAGE feature flag."
        ),
    ),
]
