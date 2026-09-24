from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://spetion:spetion@localhost:5432/spetion_exam"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "spetion"
    s3_secret_key: str = "spetion123"
    s3_bucket: str = "exam-uploads"

    # "s3" (default, MinIO/real S3 — the decided prod path) or "local" (a
    # plain-disk fallback for developing without Docker/MinIO running).
    storage_backend: str = "s3"
    local_storage_dir: str = "./local_storage"

    # Runs Celery tasks synchronously in-process instead of enqueueing to
    # Redis — only for developing without Docker/Redis running. Never the
    # default; the decided architecture never parses inline in the request.
    celery_eager: bool = False


settings = Settings()
