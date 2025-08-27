from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "dev"
    API_TITLE: str = "TurboDex API"
    API_VERSION: str = "0.1.0"
    PORT: int = 8080

    MONGO_URI: str = "mongodb://localhost:27017/turbodex"
    DB_NAME: str = "turbodex"

    JWT_SECRET: str = "my_dev_access_secret"
    JWT_REFRESH_SECRET: str = "my_dev_refresh_secret"
    JWT_ACCESS_MIN: int = 15
    JWT_REFRESH_DAYS: int = 14

    AZURE_STORAGE_CONNECTION_STRING: str = "" # Dans .env
    AZURE_BLOB_CONTAINER_RAW: str = "raw"
    AZURE_BLOB_CONTAINER_PROCESSED: str = "processed"
    AZURE_BLOB_CONTAINER_GENERIC: str = "generic"
    AZURE_BLOB_CONTAINER_AVATARS: str = "avatars"

    # Uploads
    MAX_UPLOAD_MB: int = 8
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
