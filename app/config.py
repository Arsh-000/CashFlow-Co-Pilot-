import re

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str = Field(
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY"),
    )
    SUPABASE_SERVICE_KEY: str = Field(
        validation_alias=AliasChoices("SUPABASE_SERVICE_KEY", "SUPABASE_SECRET_KEY"),
    )
    GROQ_API_KEY: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_FROM: str
    SECRET_KEY: str
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator(
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_KEY",
        "GROQ_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
        "SECRET_KEY",
        mode="before",
    )
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    @field_validator("SUPABASE_URL")
    @classmethod
    def validate_supabase_url(cls, value: str) -> str:
        if value.startswith("sb_"):
            raise ValueError(
                "SUPABASE_URL looks like an API key. Use your project URL "
                "(https://<project-ref>.supabase.co)."
            )
        if not re.match(r"^https?://", value):
            value = f"https://{value}"
        return value.rstrip("/")

    @field_validator("SUPABASE_ANON_KEY")
    @classmethod
    def validate_publishable_key(cls, value: str) -> str:
        if value.startswith("http://") or value.startswith("https://"):
            raise ValueError(
                "SUPABASE_ANON_KEY looks like a URL. Use your publishable key "
                "(sb_publishable_... or legacy anon JWT)."
            )
        return value

    @field_validator("SUPABASE_SERVICE_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if value.startswith("http://") or value.startswith("https://"):
            raise ValueError(
                "SUPABASE_SERVICE_KEY looks like a URL. Use your secret key "
                "(sb_secret_... or legacy service_role JWT)."
            )
        return value


settings = Settings()
