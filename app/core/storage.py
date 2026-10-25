"""Storage manager supporting local filesystem storage and AWS S3/MinIO."""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class StorageManager:
    """Handles persistence, asset naming, and URL generation for media files."""

    def __init__(self):
        self.local_base = settings.STORAGE_LOCAL_DIR.resolve()
        self.local_base.mkdir(parents=True, exist_ok=True)
        self.s3_client = None

        if settings.STORAGE_TYPE == "s3" and settings.S3_BUCKET_NAME:
            try:
                import boto3
                kwargs = {
                    "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
                    "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
                    "region_name": settings.AWS_REGION,
                }
                if settings.S3_ENDPOINT_URL:
                    kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

                self.s3_client = boto3.client("s3", **kwargs)
                logger.info("Configured S3 storage client for bucket: %s", settings.S3_BUCKET_NAME)
            except Exception as e:
                logger.warning("Could not initialize S3 client (%s). Falling back to local storage.", e)

    def get_task_dir(self, task_id: str) -> Path:
        """Return dedicated local directory for a given task."""
        task_dir = self.local_base / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    async def save_artifact(self, task_id: str, file_path: Path, artifact_name: str) -> str:
        """
        Store a final media artifact (e.g. video or thumbnail) and return its accessible URL.
        """
        task_dir = self.get_task_dir(task_id)
        destination = task_dir / artifact_name

        if file_path.resolve() != destination.resolve():
            shutil.copy2(file_path, destination)

        # If S3 is configured, upload to S3
        if self.s3_client and settings.STORAGE_TYPE == "s3":
            try:
                s3_key = f"videos/{task_id}/{artifact_name}"
                extra_args = {}
                if artifact_name.endswith(".mp4"):
                    extra_args["ContentType"] = "video/mp4"
                elif artifact_name.endswith(".jpg") or artifact_name.endswith(".jpeg"):
                    extra_args["ContentType"] = "image/jpeg"

                self.s3_client.upload_file(
                    str(destination),
                    settings.S3_BUCKET_NAME,
                    s3_key,
                    ExtraArgs=extra_args
                )

                if settings.S3_ENDPOINT_URL:
                    return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET_NAME}/{s3_key}"
                return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            except Exception as e:
                logger.error("Failed S3 upload, serving locally: %s", e)

        # Default local URL served by FastAPI static mount
        return f"/storage/{task_id}/{artifact_name}"

    def clean_temp_dir(self, temp_dir: Path):
        """Remove intermediate scratch render directory after pipeline completion."""
        try:
            if temp_dir.exists() and temp_dir.is_dir():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning("Failed to clean temp directory %s: %s", temp_dir, e)


storage_manager = StorageManager()
