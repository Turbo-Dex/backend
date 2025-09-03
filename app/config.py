# app/config.py
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Métadonnées API ---
    API_TITLE: str = "Turbodex API"
    API_VERSION: str = "0.1.0"
    APP_ENV: str = "dev"

    # --- CORS ---
    CORS_ALLOW_ORIGINS: List[str] = ["*"]

    # --- JWT ---
    JWT_SECRET: str = "dev-secret"
    JWT_REFRESH_SECRET: str = "dev-refresh-secret"
    JWT_ACCESS_MIN: int = 15
    JWT_REFRESH_DAYS: int = 7

    # --- Mongo ---
    MONGO_URI: str | None = None 
    DB_NAME: str = "turbodex"

    # --- Azure Storage ---
    AZURE_STORAGE_CONN: str | None = None
    AZURE_STORAGE_ACCOUNT: str | None = None
    AZURE_STORAGE_KEY: str | None = None
    AZURE_BLOB_CONTAINER_RAW: str = "raw"
    AZURE_BLOB_CONTAINER_PROCESSED: str = "processed"
    AZURE_QUEUE_NAME: str = "process-image"

    # --- URLs IA ---
    IA_BLUR_URL: str | None = None
    IA_PREDICT_URL: str | None = None     # ex: "http://20.19.112.183/predict/"

    # --- Timeout HTTP ---
    HTTP_TIMEOUT_SECONDS: float = 20.0

    # Pydantic v2 — remplace class Config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",   # ignore les variables env inconnues
    )

settings = Settings()

