import aioboto3
from app.core.config import settings

async def upload_file_to_s3(file_data: bytes, object_name: str, content_type: str = "application/pdf") -> str:
    """
    Uploads a file to MinIO/S3 and returns a presigned URL valid for 7 days.
    """
    session = aioboto3.Session()
    async with session.client( # type: ignore
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY.get_secret_value(),
        region_name="us-east-1"  # typically ignored by minio but required by boto3
    ) as s3:
        await s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=object_name,
            Body=file_data,
            ContentType=content_type
        )
        
        # Generate presigned URL
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": object_name},
            ExpiresIn=7 * 24 * 3600  # 7 days
        )
        return url
