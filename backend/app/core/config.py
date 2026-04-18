import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "Evernest CRM API")
        self.api_v1_prefix = os.getenv("API_V1_PREFIX", "/api/v1")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.audit_stale_lead_hours = int(os.getenv("AUDIT_STALE_LEAD_HOURS", "72"))
        self.audit_no_follow_up_hours = int(os.getenv("AUDIT_NO_FOLLOW_UP_HOURS", "24"))
        self.audit_unassigned_active_lead_hours = int(
            os.getenv("AUDIT_UNASSIGNED_ACTIVE_LEAD_HOURS", "24")
        )
        self.whatsapp_verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        self.whatsapp_app_secret = os.getenv("WHATSAPP_APP_SECRET", "")
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/evernest_crm",
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
