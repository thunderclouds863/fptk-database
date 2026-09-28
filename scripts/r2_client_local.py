# scripts/r2_client_local.py
import os
from dotenv import load_dotenv
import boto3
from botocore.config import Config

load_dotenv()

s3 = boto3.client(
    service_name="s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
    config=Config(signature_version="s3v4"),
)

R2_BUCKET = os.environ["R2_BUCKET_NAME"]