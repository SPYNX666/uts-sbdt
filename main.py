"""
UTS Sistem Basis Data Terdistribusi — Backend API
==================================================
Arsitektur:
  - engine_primary  → PostgreSQL Primary  (WRITE)
  - engine_replica  → PostgreSQL Replica  (READ)
  - JWT HS256       → validasi Bearer token (dev mode)
                      (untuk production: validasi RS256 via Keycloak JWKS)
"""

import os
import uuid
import random
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, DateTime, Float, JSON, String, Text, create_engine, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ═══════════════════════════════════════════════════════════════
# 1. KONFIGURASI (dibaca dari environment / docker-compose)
# ═══════════════════════════════════════════════════════════════
# Konfigurasi Database (bisa via DB_HOST/DB_PORT atau langsung DATABASE_URL)
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres_password")
DB_HOST = os.getenv("DB_HOST", "db-primary")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "uts_sbd")

REPLICA_DB_HOST = os.getenv("REPLICA_DB_HOST", "db-replica")
REPLICA_DB_PORT = os.getenv("REPLICA_DB_PORT", "5432")

_DEFAULT_PRIMARY_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
_DEFAULT_REPLICA_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{REPLICA_DB_HOST}:{REPLICA_DB_PORT}/{DB_NAME}"

_RAW_DB_URL = os.getenv("DATABASE_URL", _DEFAULT_PRIMARY_URL)
_RAW_REPLICA_URL = os.getenv("REPLICA_DATABASE_URL", _DEFAULT_REPLICA_URL)

def _ensure_psycopg2_dialect(url: str) -> str:
    """
    Pastikan URL menggunakan dialek postgresql+psycopg2://.
    Fungsi ini menangani kasus di mana env var docker-compose
    hanya mengisi 'postgresql://' tanpa menyebut driver-nya.
    """
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1) \
                  .replace("postgres://", "postgresql+psycopg2://", 1)
    return url  # sudah benar, misal postgresql+psycopg2://...

DATABASE_URL       = _ensure_psycopg2_dialect(_RAW_DB_URL)
REPLICA_DATABASE_URL = _ensure_psycopg2_dialect(_RAW_REPLICA_URL)
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "uts-sbd")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-ganti-di-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
APP_ENV = os.getenv("APP_ENV", "development")


# ═══════════════════════════════════════════════════════════════
# 2. DATABASE ENGINES
#    Primary  → untuk operasi WRITE (INSERT, UPDATE, DELETE)
#    Replica  → untuk operasi READ  (SELECT)
# ═══════════════════════════════════════════════════════════════
engine_primary = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,       # cek koneksi sebelum dipakai
    pool_size=5,
    max_overflow=10,
    echo=(APP_ENV == "development"),
)

engine_replica = create_engine(
    REPLICA_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=(APP_ENV == "development"),
)

SessionPrimary = sessionmaker(autocommit=False, autoflush=False, bind=engine_primary)
SessionReplica  = sessionmaker(autocommit=False, autoflush=False, bind=engine_replica)


# ═══════════════════════════════════════════════════════════════
# 3. ORM MODEL
# ═══════════════════════════════════════════════════════════════
class Base(DeclarativeBase):
    pass


class Prediction(Base):
    __tablename__ = "predictions"

    id         = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(String(255), nullable=False, index=True)
    input_data = Column(JSON, nullable=False)
    result     = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=True)
    notes      = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ═══════════════════════════════════════════════════════════════
# 4. PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════
class PredictRequest(BaseModel):
    input_data: dict[str, Any] = Field(
        ...,
        example={"age": 30, "income": 50000, "credit_score": 720},
    )
    notes: Optional[str] = Field(None, example="Prediksi untuk nasabah baru")


class PredictResponse(BaseModel):
    id: str
    user_id: str
    result: str
    confidence: float
    notes: Optional[str]
    created_at: datetime
    written_to: str = "primary"       # transparansi: data ditulis ke primary

    model_config = {"from_attributes": True}


class HistoryItem(BaseModel):
    id: str
    user_id: str
    input_data: dict[str, Any]
    result: str
    confidence: Optional[float]
    notes: Optional[str]
    created_at: datetime
    read_from: str = "replica"        # transparansi: data dibaca dari replica

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str
    environment: str
    db_primary: str
    db_replica: str


# ═══════════════════════════════════════════════════════════════
# 5. FASTAPI APP
# ═══════════════════════════════════════════════════════════════
app = FastAPI(
    title="UTS Sistem Basis Data Terdistribusi",
    description=(
        "Backend API dengan arsitektur **Primary-Replica** PostgreSQL.\n\n"
        "- `POST /predict` → tulis ke **Primary**\n"
        "- `GET /history`  → baca dari **Replica**\n"
        "- Autentikasi via **Bearer JWT** (HS256 dev / RS256 Keycloak prod)"
    ),
    version="1.0.0",
)


# ═══════════════════════════════════════════════════════════════
# 6. DATABASE DEPENDENCIES (Dependency Injection)
# ═══════════════════════════════════════════════════════════════
def get_primary_db() -> Session:
    """Dependency → session ke PostgreSQL PRIMARY (write)."""
    db = SessionPrimary()
    try:
        yield db
    finally:
        db.close()


def get_replica_db() -> Session:
    """Dependency → session ke PostgreSQL REPLICA (read-only)."""
    db = SessionReplica()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# 7. AUTENTIKASI — JWT Bearer Token
#    Mode dev  : HS256, divalidasi dengan SECRET_KEY
#    Mode prod  : RS256, pubkey diambil dari Keycloak JWKS endpoint
#                 URL: {KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs
# ═══════════════════════════════════════════════════════════════
security = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Validasi Bearer token dari header Authorization.
    Mendukung:
      - Token Keycloak RS256 (asymmetric SSO)
      - Token Dev HS256 (symmetric SECRET_KEY)
    """
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "RS256":
            # Token dari Keycloak SSO
            payload = jwt.get_unverified_claims(token)
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token Keycloak sudah kedaluwarsa.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # Token internal dev (HS256)
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )

        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token tidak valid: klaim 'sub' tidak ditemukan.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    except HTTPException:
        raise
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token tidak valid atau sudah kedaluwarsa: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ═══════════════════════════════════════════════════════════════
# 8. STARTUP — Buat tabel jika belum ada
# ═══════════════════════════════════════════════════════════════
@app.on_event("startup")
def on_startup() -> None:
    """Buat semua tabel di PRIMARY saat aplikasi start."""
    Base.metadata.create_all(bind=engine_primary)


# ═══════════════════════════════════════════════════════════════
# 9. ENDPOINTS
# ═══════════════════════════════════════════════════════════════

# ── 9.1 Health Check ──────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health_check() -> HealthResponse:
    """
    Cek status API dan konektivitas ke kedua database.
    Tidak memerlukan autentikasi.
    """
    # Ping primary
    try:
        with engine_primary.connect() as conn:
            conn.execute(text("SELECT 1"))
        primary_status = "connected"
    except Exception as exc:
        primary_status = f"error: {exc}"

    # Ping replica
    try:
        with engine_replica.connect() as conn:
            conn.execute(text("SELECT 1"))
        replica_status = "connected"
    except Exception as exc:
        replica_status = f"error: {exc}"

    return HealthResponse(
        status="OK",
        timestamp=datetime.utcnow().isoformat(),
        service="uts-sbd-api",
        environment=APP_ENV,
        db_primary=primary_status,
        db_replica=replica_status,
    )


# ── 9.2 POST /predict ─────────────────────────────────────────
@app.post(
    "/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Prediction"],
    summary="Jalankan prediksi & simpan ke Primary",
)
def create_prediction(
    body: PredictRequest,
    token_payload: dict = Depends(verify_token),   # ← wajib Bearer token
    db: Session = Depends(get_primary_db),         # ← tulis ke PRIMARY
) -> PredictResponse:
    """
    **Alur:**
    1. Validasi Bearer token (`Authorization: Bearer <token>`)
    2. Ekstrak `user_id` dari klaim `sub`
    3. Jalankan logika prediksi (mock — ganti dengan model ML nyata)
    4. Simpan hasil ke tabel `predictions` di **PostgreSQL Primary**
    5. Kembalikan data prediksi

    > ⚠️ Endpoint ini memerlukan header `Authorization: Bearer <token>`
    """
    user_id: str = token_payload["sub"]

    # ── Mock prediction logic ──────────────────────────────────
    # Ganti blok ini dengan pemanggilan model ML / logika bisnis nyata.
    labels = ["approved", "rejected", "review_needed"]
    result = random.choice(labels)
    confidence = round(random.uniform(0.70, 0.99), 4)
    # ──────────────────────────────────────────────────────────

    # Simpan ke PRIMARY
    prediction = Prediction(
        user_id=user_id,
        input_data=body.input_data,
        result=result,
        confidence=confidence,
        notes=body.notes,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return PredictResponse(
        id=str(prediction.id),
        user_id=prediction.user_id,
        result=prediction.result,
        confidence=prediction.confidence,
        notes=prediction.notes,
        created_at=prediction.created_at,
        written_to="primary",
    )


# ── 9.3 GET /history ──────────────────────────────────────────
@app.get(
    "/history",
    response_model=list[HistoryItem],
    tags=["Prediction"],
    summary="Ambil riwayat prediksi dari Replica",
)
def get_history(
    token_payload: dict = Depends(verify_token),  # ← wajib Bearer token
    db: Session = Depends(get_replica_db),        # ← baca dari REPLICA
    limit: int = Query(10, ge=1, le=100, description="Jumlah data per halaman"),
    offset: int = Query(0, ge=0, description="Offset untuk pagination"),
) -> list[HistoryItem]:
    """
    **Alur:**
    1. Validasi Bearer token
    2. Ekstrak `user_id` dari klaim `sub` (user hanya bisa lihat miliknya sendiri)
    3. Query tabel `predictions` dari **PostgreSQL Replica** (read-only)
    4. Kembalikan daftar prediksi terurut dari terbaru

    **Query params:** `?limit=10&offset=0` untuk pagination.

    > ⚠️ Endpoint ini memerlukan header `Authorization: Bearer <token>`
    """
    user_id: str = token_payload["sub"]

    # Baca dari REPLICA
    rows = (
        db.query(Prediction)
        .filter(Prediction.user_id == user_id)
        .order_by(Prediction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        HistoryItem(
            id=str(row.id),
            user_id=row.user_id,
            input_data=row.input_data,
            result=row.result,
            confidence=row.confidence,
            notes=row.notes,
            created_at=row.created_at,
            read_from="replica",
        )
        for row in rows
    ]


# ── 9.4 Root ──────────────────────────────────────────────────
@app.get("/", tags=["Root"])
def root() -> dict:
    return {
        "message": "UTS Sistem Basis Data Terdistribusi API",
        "docs": "/docs",
        "health": "/health",
    }
