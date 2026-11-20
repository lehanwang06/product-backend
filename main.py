import os

import boto3
import psycopg2
from botocore.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Product APIs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*s"],
)

# All settings come from environment variables (nothing hardcoded)
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "productsdb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.environ["DB_PASSWORD"]
S3_BUCKET = os.environ["S3_BUCKET"]
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    config=Config(signature_version="s3v4"),
)


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5,
    )


def make_image_url(key: str) -> str:
    # Presigned URL: valid for 1 hour, bucket can stay private
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=3600,
    )


def to_product(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "price": float(row["price"]),
        "image_url": make_image_url(row["image_s3_key"]),
    }


@app.get("/health")
def health():
    # Handy for the ALB health check
    return {"status": "ok"}


@app.get("/products")
def list_products():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, description, category, price, image_s3_key "
                "FROM products ORDER BY id"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [to_product(r) for r in rows]


@app.get("/products/{product_id}")
def get_product(product_id: int):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, description, category, price, image_s3_key "
                "FROM products WHERE id = %s",
                (product_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return to_product(row)
