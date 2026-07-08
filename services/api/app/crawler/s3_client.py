import uuid
import gzip
import hashlib
import aioboto3
from app.core.config import settings

session = aioboto3.Session()

async def upload_html(audit_id: uuid.UUID, url: str, html_content: bytes):
    """
    Compresses HTML content and uploads it to S3.
    """
    url_hash = hashlib.sha1(url.encode('utf-8')).hexdigest()
    key = f"snapshots/{audit_id}/{url_hash}.html.gz"
    
    compressed_content = gzip.compress(html_content)
    
    async with session.client(  # type: ignore
        's3',
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY.get_secret_value()
    ) as s3_client:
        await s3_client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=compressed_content,
            ContentType='text/html',
            ContentEncoding='gzip'
        )
