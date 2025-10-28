from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database configuration
    database_url: str

    # Storage configuration (MinIO/S3 compatible)
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str

    class Config:
        env_prefix = ''
        env_file = '.env'
        env_file_encoding = 'utf-8'

