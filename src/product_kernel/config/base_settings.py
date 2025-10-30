# src/product_kernel/config/base_settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseAppSettings(BaseSettings):
    """
    Shared base settings for all applications.
    Each app (e.g., TOS, PetCare) can subclass and extend it.
    """

    database_url: str | None = None
    secret_key: str = "dev-secret-key"
    cors_allow_origins: str | None = "*"
    app_name: str = "Product App"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def DB_URL(self) -> str:
        """Backward compatible accessor."""
        return self.database_url or ""

    @property
    def SECRET_KEY(self) -> str:
        return self.secret_key
