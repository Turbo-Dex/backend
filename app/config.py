# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # --- Champs "source of truth" en snake_case ---
    # App
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    api_title: str = Field(default="TurboDex API", alias="API_TITLE")
    api_prefix: str = Field(default="/v1", alias="API_PREFIX")

    # Mongo
    mongo_uri: str = Field(default="mongodb://localhost:27017/turbodex", alias="MONGO_URI")
    db_name: str = Field(default="turbodex", alias="DB_NAME")

    # JWT
    jwt_secret: str = Field(default="dev_secret", alias="JWT_SECRET")
    jwt_refresh_secret: str = Field(default="dev_refresh", alias="JWT_REFRESH_SECRET")
    jwt_access_min: int = Field(default=15, alias="JWT_ACCESS_MIN")
    jwt_refresh_days: int = Field(default=14, alias="JWT_REFRESH_DAYS")

    # Azure Storage
    azure_storage_connection_string: str = Field(default="", alias="AZURE_STORAGE_CONNECTION_STRING")
    azure_blob_container_raw: str = Field(default="raw", alias="AZURE_BLOB_CONTAINER_RAW")
    azure_blob_container_processed: str = Field(default="processed", alias="AZURE_BLOB_CONTAINER_PROCESSED")
    azure_blob_container_generic: str = Field(default="generic", alias="AZURE_BLOB_CONTAINER_GENERIC")
    azure_blob_container_avatars: str = Field(default="avatars", alias="AZURE_BLOB_CONTAINER_AVATARS")

    # Uploads
    max_upload_mb: int = Field(default=8, alias="MAX_UPLOAD_MB")

    # CORS
    cors_origins: str | None = Field(default=None, alias="CORS_ORIGINS")

    # Pydantic Settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        case_sensitive=False,
        extra="ignore",
    )

    # --- Propriétés "back-compat" en UPPERCASE (pour ne rien toucher ailleurs) ---
    @property
    def APP_ENV(self) -> str: return self.app_env
    @property
    def APP_VERSION(self) -> str: return self.app_version
    @property
    def API_TITLE(self) -> str: return self.api_title
    @property
    def API_PREFIX(self) -> str: return self.api_prefix
    @property
    def API_VERSION(self) -> str: return self.app_version

    @property
    def MONGO_URI(self) -> str: return self.mongo_uri
    @property
    def DB_NAME(self) -> str: return self.db_name

    @property
    def JWT_SECRET(self) -> str: return self.jwt_secret
    @property
    def JWT_REFRESH_SECRET(self) -> str: return self.jwt_refresh_secret
    @property
    def JWT_ACCESS_MIN(self) -> int: return self.jwt_access_min
    @property
    def JWT_REFRESH_DAYS(self) -> int: return self.jwt_refresh_days

    @property
    def AZURE_STORAGE_CONNECTION_STRING(self) -> str: return self.azure_storage_connection_string
    @property
    def AZURE_BLOB_CONTAINER_RAW(self) -> str: return self.azure_blob_container_raw
    @property
    def AZURE_BLOB_CONTAINER_PROCESSED(self) -> str: return self.azure_blob_container_processed
    @property
    def AZURE_BLOB_CONTAINER_GENERIC(self) -> str: return self.azure_blob_container_generic
    @property
    def AZURE_BLOB_CONTAINER_AVATARS(self) -> str: return self.azure_blob_container_avatars

    @property
    def MAX_UPLOAD_MB(self) -> int: return self.max_upload_mb
    @property
    def CORS_ORIGINS(self) -> str | None: return self.cors_origins

settings = Settings()


