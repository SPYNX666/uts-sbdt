# ============================================================
# Stage 1 — Builder
# Install semua dependencies ke virtual environment.
# Layer ini tidak masuk ke image final.
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools yang dibutuhkan psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Buat virtual environment terisolasi
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Cache layer: install deps hanya jika requirements.txt berubah
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ============================================================
# Stage 2 — Runner
# Image final yang ringan: hanya berisi runtime + app.
# Tidak ada gcc, header files, atau cache pip.
# ============================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Runtime dependency psycopg2 (libpq5 saja, bukan dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Salin virtual environment dari stage builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Salin source code aplikasi
COPY main.py .

# Env default (akan di-override oleh docker-compose)
ENV APP_ENV=production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Buat user non-root untuk keamanan
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 8000

# Health check bawaan Docker
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Jalankan Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
