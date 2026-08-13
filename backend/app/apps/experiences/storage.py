from functools import lru_cache

import boto3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def r2_is_configured() -> bool:
    return all((
        settings.R2_ACCOUNT_ID,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
        settings.R2_BUCKET_NAME,
    ))


@lru_cache
def get_r2_client():
    if not r2_is_configured():
        raise ImproperlyConfigured("Cloudflare R2 is not configured.")

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )
