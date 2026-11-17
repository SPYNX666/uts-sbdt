#!/bin/bash
# =============================================================
# PostgreSQL Replica — Custom Entrypoint
# Dijalankan setiap kali container start.
# Jika PGDATA kosong → jalankan pg_basebackup dari primary.
# Jika sudah ada data → langsung start postgres sebagai standby.
# =============================================================
set -e

PRIMARY_HOST="${PRIMARY_HOST:-db-primary}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"
REPLICATION_USER="${REPLICATION_USER:-replicator}"
REPLICATION_PASSWORD="${REPLICATION_PASSWORD:-replicator_password}"
PGDATA="${PGDATA:-/var/lib/postgresql/data}"

# Helper untuk menjalankan perintah sebagai user postgres (bukan root)
run_as_postgres() {
  if [ "$(id -u)" = '0' ]; then
    if command -v gosu >/dev/null 2>&1; then
      gosu postgres "$@"
    else
      su -s /bin/bash postgres -c "$*"
    fi
  else
    "$@"
  fi
}

echo ">>> [REPLICA] Menunggu primary (${PRIMARY_HOST}:${PRIMARY_PORT}) siap..."
export PGPASSWORD="$REPLICATION_PASSWORD"

until pg_isready -h "$PRIMARY_HOST" -p "$PRIMARY_PORT" -U "$REPLICATION_USER"; do
  echo ">>> [REPLICA] Primary belum siap, coba lagi dalam 3 detik..."
  sleep 3
done

echo ">>> [REPLICA] Primary sudah siap!"

# Pastikan folder data dimiliki oleh user postgres
mkdir -p "$PGDATA"
if [ "$(id -u)" = '0' ]; then
  chown -R postgres:postgres "$PGDATA"
  chmod 700 "$PGDATA"
fi

# Cek apakah data directory sudah terisi (bukan first run)
if [ -z "$(ls -A "$PGDATA" 2>/dev/null)" ]; then
  echo ">>> [REPLICA] PGDATA kosong. Menjalankan pg_basebackup dari primary..."

  # Jalankan pg_basebackup sebagai user postgres agar permission file benar
  # Flag -R → otomatis buat standby.signal + tulis primary_conninfo
  run_as_postgres pg_basebackup \
    -h "$PRIMARY_HOST" \
    -p "$PRIMARY_PORT" \
    -U "$REPLICATION_USER" \
    -D "$PGDATA" \
    --format=plain \
    --wal-method=stream \
    --progress \
    --verbose \
    -R

  # Tambahkan konfigurasi koneksi ke primary (jika belum ada dari -R)
  cat >> "$PGDATA/postgresql.auto.conf" <<EOF

# --- Konfigurasi Standby (ditambahkan oleh entrypoint.sh) ---
primary_conninfo = 'host=${PRIMARY_HOST} port=${PRIMARY_PORT} user=${REPLICATION_USER} password=${REPLICATION_PASSWORD} application_name=replica1'
promote_trigger_file = '/tmp/promote_trigger'
recovery_min_apply_delay = 0
EOF

  if [ "$(id -u)" = '0' ]; then
    chown -R postgres:postgres "$PGDATA"
    chmod 700 "$PGDATA"
  fi

  echo ">>> [REPLICA] pg_basebackup selesai. Memulai sebagai standby..."
else
  echo ">>> [REPLICA] Data sudah ada. Memulai postgres langsung..."
fi

unset PGPASSWORD

# Hapus sisa file lock jika container sempat restart paksa
rm -f "$PGDATA/postmaster.pid"

# Jalankan server postgres sebagai user postgres (PostgreSQL melarang dijalankan sebagai root!)
if [ "$(id -u)" = '0' ]; then
  if command -v gosu >/dev/null 2>&1; then
    exec gosu postgres postgres
  else
    exec su -s /bin/bash postgres -c "exec postgres"
  fi
else
  exec postgres
fi
