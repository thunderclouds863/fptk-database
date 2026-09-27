# core/r2_storage.py
import boto3
import base64
import mimetypes
from botocore.config import Config
import streamlit as st


class R2Storage:
    def __init__(self):
        try:
            config = st.secrets["connections"]["r2"]
            self.account_id = config["account_id"]
            self.bucket = config["recruitment-files"]
            self.public_url = config.get("public_url", "").rstrip("/")
            self.access_key = config["access_key_id"]
            self.secret_key = config["secret_access_key"]
        except KeyError as e:
            st.error(f"❌ Konfigurasi R2 tidak ditemukan di secrets: {e}")
            raise

        self.client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",  # R2 harus menggunakan auto
            config=Config(signature_version="s3v4"),
        )

    def upload_bytes(self, file_bytes: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        """Upload file biner ke R2."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return key

    def upload_base64(self, base64_data: str, key: str, content_type: str = None) -> str:
        """Upload string base64 ke R2 (kompatibel dengan migrasi data lama)."""
        if base64_data.startswith("data:") and "," in base64_data:
            header, base64_data = base64_data.split(",", 1)
            if content_type is None and ";" in header:
                content_type = header.split(":")[1].split(";")[0]

        file_bytes = base64.b64decode(base64_data)

        if content_type is None:
            ext = key.rsplit(".", 1)[-1] if "." in key else ""
            content_type = mimetypes.types_map.get(f".{ext}", "application/octet-stream")

        return self.upload_bytes(file_bytes, key, content_type)

    def download_bytes(self, key: str) -> bytes:
        """Download file dari R2, kembalikan bytes."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Hasilkan URL akses sementara (untuk file privat)."""
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, key: str):
        """Hapus file."""
        self.client.delete_object(Bucket=self.bucket, Key=key)


@st.cache_resource
def get_r2() -> R2Storage:
    """Inisialisasi singleton, cache client global untuk menghindari pembuatan berulang."""
    return R2Storage()
