"""L3：從 `.env` 載入 API 層設定（pydantic-settings）。

敏感欄位使用 `SecretStr`，**勿**對整份 `ApiSettings` 做 `print`／`model_dump` 寫入 log；
`/health` 只暴露布林與非敏感路徑字串。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="GOOGLE_API_KEY",
    )
    langsmith_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="LANGSMITH_API_KEY",
    )
    langsmith_tracing: bool = Field(default=False, validation_alias="LANGSMITH_TRACING")
    langsmith_project: str | None = Field(default=None, validation_alias="LANGSMITH_PROJECT")
    checkpoint_db: str = Field(
        default="data/langgraph_checkpoints.sqlite",
        validation_alias="LANGGRAPH_CHECKPOINT_DB",
    )

    def google_api_key_configured(self) -> bool:
        k = self.google_api_key
        return bool(k and k.get_secret_value().strip())

    def langsmith_api_key_configured(self) -> bool:
        k = self.langsmith_api_key
        return bool(k and k.get_secret_value().strip())


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
