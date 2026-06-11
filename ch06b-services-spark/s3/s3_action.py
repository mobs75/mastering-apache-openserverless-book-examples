"""
s3_action.py — OpenServerless action using SeaweedFS/S3 built-in service.
Chapter 13 — Mastering Apache OpenServerless

SeaweedFS is S3-compatible and replaces MinIO in recent OpenServerless installs.
Available at: seaweedfs.nuvolaris.svc.cluster.local:9000

boto3 (v1.35.98) is pre-installed in the python:3.11 runtime.

IMPORTANT:
  - signature_version='s3v4' is mandatory
  - region_name='us-east-1' is required by boto3 but ignored by SeaweedFS
  - Content must be a string (or bytes) before upload — dict will fail

Deploy:
    ops action create s3-demo s3_action.py --kind python:3.11

Test:
    ops action invoke s3-demo --result --param cmd list-buckets
    ops action invoke s3-demo --result --param cmd create-bucket --param bucket myapp
    ops action invoke s3-demo --result --param cmd put \
        --param bucket myapp --param key data/test.txt --param content "Hello S3"
    ops action invoke s3-demo --result --param cmd list --param bucket myapp
    ops action invoke s3-demo --result --param cmd get \
        --param bucket myapp --param key data/test.txt
"""
import boto3
import json
import os
from botocore.client import Config


S3_ENDPOINT = os.environ.get('S3_ENDPOINT', 'http://seaweedfs.nuvolaris.svc.cluster.local:9000')
S3_KEY      = os.environ.get('S3_ACCESS_KEY', 'nuvolaris')
S3_SECRET   = os.environ.get('S3_SECRET_KEY', '')


def get_client():
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_KEY,
        aws_secret_access_key=S3_SECRET,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'  # Required by boto3, ignored by SeaweedFS
    )


def main(args: dict) -> dict:
    cmd    = args.get('cmd', 'list-buckets')
    bucket = args.get('bucket', 'myapp')
    key    = args.get('key', '')
    s3     = get_client()

    if cmd == 'list-buckets':
        response = s3.list_buckets()
        buckets = [b['Name'] for b in response.get('Buckets', [])]
        return {'result': buckets}

    elif cmd == 'create-bucket':
        s3.create_bucket(Bucket=bucket)
        return {'result': f'bucket {bucket} created'}

    elif cmd == 'put':
        content = args.get('content', '')
        # Always serialize to string — dict content will cause encode() error
        if isinstance(content, dict):
            content = json.dumps(content)
        s3.put_object(Bucket=bucket, Key=key, Body=content.encode('utf-8'))
        return {'bucket': bucket, 'key': key, 'result': 'uploaded'}

    elif cmd == 'get':
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        return {'key': key, 'result': content}

    elif cmd == 'list':
        response = s3.list_objects_v2(Bucket=bucket)
        keys = [obj['Key'] for obj in response.get('Contents', [])]
        return {'result': keys}

    elif cmd == 'delete':
        s3.delete_object(Bucket=bucket, Key=key)
        return {'key': key, 'result': 'deleted'}

    else:
        return {'error': f'Unknown command: {cmd}. Supported: list-buckets, create-bucket, put, get, list, delete'}
