import configparser
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from botocore.response import StreamingBody

from shared.config.settings import get_settings


class S3BucketService:
    def __init__(self) -> None:

        settings = get_settings()
        self.bucket_name = "your-bucket-name"  # Можешь вынести в настройки
        self.endpoint = settings.minio_settings.endpoint_url
        self.access_key = settings.minio_settings.minio_root_user
        self.secret_key = settings.minio_settings.minio_root_password
        self.secure = settings.minio_settings.minio_secure

    def create_s3_client(self) -> boto3.client:
        client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
        )
        return client

    def upload_file_object(
        self,
        prefix: str,
        source_file_name: str,
        content: Union[str, bytes],
    ) -> None:
        client = self.create_s3_client()
        destination_path = str(Path(prefix, source_file_name))

        if isinstance(content, bytes):
            buffer = BytesIO(content)
        else:
            buffer = BytesIO(content.encode("utf-8"))
        client.upload_fileobj(buffer, self.bucket_name, destination_path)

    def list_objects(self, prefix: str) -> list[str]:
        client = self.create_s3_client()

        response = client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
        storage_content: list[str] = []

        try:
            contents = response["Contents"]
        except KeyError:
            return storage_content

        for item in contents:
            storage_content.append(item["Key"])

        return storage_content

    def delete_file_object(self, prefix: str, source_file_name: str) -> None:
        client = self.create_s3_client()
        path_to_file = str(Path(prefix, source_file_name))
        client.delete_object(Bucket=self.bucket_name, Key=path_to_file)