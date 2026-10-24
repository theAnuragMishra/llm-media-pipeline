"""Application configuration via Pydantic Settings."""

import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for media processing pipeline microservice."""

    # Base Application Settings
    APP_NAME: str = "CourseVideoPipeline"
    APP_ENV: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    DEBUG: bool = True

    # Base Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    STORAGE_LOCAL_DIR: Path = Path("./storage")
    TEMP_DIR: Path = Path("./temp_renders")

    # Message Broker Configuration ('rabbitmq' or 'memory')
    BROKER_TYPE: Literal["rabbitmq", "memory"] = "memory"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_QUEUE: str = "video.generate.jobs"
    RABBITMQ_EXCHANGE: str = "media.pipeline.exchange"
    RABBITMQ_ROUTING_KEY: str = "video.generate"
    RABBITMQ_PREFETCH_COUNT: int = 1

    # Redis (used for distributed pub/sub event broadcasting & task status tracking)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage Backend (local filesystem or S3/MinIO)
    STORAGE_TYPE: Literal["local", "s3"] = "local"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET_NAME: str = "course-videos"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"

    # LLM Settings for Script Generation (API Key is strictly required)
    LLM_PROVIDER: Literal["openai", "gemini"] = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    LLM_BASE_URL: str | None = None

    # TTS Settings for Audio Synthesis
    TTS_PROVIDER: Literal["edge_tts", "openai"] = "edge_tts"
    TTS_VOICE: str = "en-US-ChristopherNeural"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure directories exist
settings.STORAGE_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
