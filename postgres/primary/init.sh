#!/bin/bash
# =============================================================
# PostgreSQL Primary — Init Script
# Dijalankan SEKALI saat container pertama kali dibuat.
# Tugasnya: buat user replikasi + konfigurasi WAL.
# =============================================================
set -e

echo ">>> [PRIMARY] Membuat user replikasi: ${REPLICATION_USER}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Buat user khusus replikasi
    CREATE USER ${REPLICATION_USER}
        WITH REPLICATION
        ENCRYPTED PASSWORD '${REPLICATION_PASSWORD}';

    -- (Opsional) Buat database tambahan jika dibutuhkan
    -- CREATE DATABASE uts_sbd_analytics;
EOSQL

echo ">>> [PRIMARY] Mengkonfigurasi pg_hba.conf untuk replikasi..."
# Izinkan user replicator dari network manapun di Docker
cat >> "$PGDATA/pg_hba.conf" <<EOF

# Replication access — allow replicator from Docker network
host    replication     ${REPLICATION_USER}     0.0.0.0/0     md5
EOF

echo ">>> [PRIMARY] Mengkonfigurasi postgresql.conf untuk WAL Streaming..."
cat >> "$PGDATA/postgresql.conf" <<EOF

# --- Konfigurasi Replikasi (ditambahkan oleh init.sh) ---
wal_level = replica
max_wal_senders = 5
max_replication_slots = 5
wal_keep_size = 128
hot_standby = on
synchronous_commit = on
EOF

echo ">>> [PRIMARY] Inisialisasi selesai. Restart diperlukan agar konfigurasi aktif."
