"""Integration credentials are read on the server only."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    google_client_id: str = ""
    google_client_secret: str = ""
    google_calendar_redirect_uri: str = "http://localhost:8000/api/v1/calendar/callback"
    token_encryption_key: str = ""
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""
    llm_max_output_tokens: int = Field(default=1500, ge=1, le=8192)
    global_ai_daily_call_cap: int = Field(default=500, ge=0)
    extension_id: str = ""

    @property
    def calendar_configured(self) -> bool:
        return bool(
            self.google_client_id and self.google_client_secret and self.token_encryption_key
        )

    @property
    def ai_configured(self) -> bool:
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key and self.anthropic_model)
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key and self.gemini_model)
        return False
