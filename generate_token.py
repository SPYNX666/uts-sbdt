#!/usr/bin/env python3
"""
generate_token.py — Generator JWT Token menggunakan PURE Python Standard Library.
Tanpa perlu install library eksternal (jose/jwt). Bisa dijalankan di Python manapun.
"""
import base64
import hashlib
import hmac
import json
import sys
import time

SECRET_KEY = "dev-secret-key-ganti-di-production"


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def create_jwt(user_id: str, email: str, expires_in_seconds: int = 86400) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + expires_in_seconds,
        "iss": "uts-sbd-dev",
    }

    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{header_b64}.{payload_b64}".encode("utf-8")

    signature = hmac.new(SECRET_KEY.encode("utf-8"), message, hashlib.sha256).digest()
    sig_b64 = b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else "admin"
    email = sys.argv[2] if len(sys.argv) > 2 else "admin@example.com"
    token = create_jwt(user_id, email)
    print(token)
