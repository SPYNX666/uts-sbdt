LAPORAN TUGAS TENGAH SEMESTER (UTS)
SISTEM BASIS DATA TERDISTRIBUSI

TOPIK:
IMPLEMENTASI BASIS DATA TERDISTRIBUSI DENGAN REPLIKASI PRIMARY-REPLICA, KEAMANAN SINGLE SIGN-ON (SSO), SERTA ORKESTRASI KONTAINER BERBASIS DOCKER DAN KUBERNETES


DISUSUN OLEH:
Nama Lengkap: Erlan Reza Asefi
Nomor Induk Mahasiswa (NIM): 20230801122
Mata Kuliah: Sistem Basis Data Terdistribusi
Kelas: [Isi Kelas Anda, contoh: IF-45-01]
Program Studi: Teknik Informatika / Sistem Informasi
Fakultas: Fakultas Ilmu Komputer
Perguruan Tinggi: [Isi Nama Universitas Anda]
Tahun Akademik: 2026/2027

================================================================================

DAFTAR ISI

BAB 1: PENDAHULUAN
1.1 Latar Belakang
1.2 Rumusan Masalah dan Tujuan

BAB 2: ARSITEKTUR SISTEM DAN TOPOLOGI
2.1 Deskripsi Komponen Sistem
2.2 Alur dan Topologi Sistem
2.3 Mekanisme Pemisahan Baca dan Tulis (Read/Write Splitting)

BAB 3: TAHAP 1 - KONTAINERISASI DOCKER
3.1 Perancangan Dockerfile Multi-Stage
3.2 Orkestrasi Layanan dengan Docker Compose
3.3 Bukti Eksekusi Kontainer Docker

BAB 4: TAHAP 2 - ORKESTRASI KUBERNETES (MINIKUBE)
4.1 Peran StatefulSet dalam Basis Data Terdistribusi
4.2 Manajemen Persistensi dengan PersistentVolumeClaim (PVC)
4.3 Pemisahan Konfigurasi dan Kredensial (ConfigMap dan Secret)
4.4 Status Penyebaran Beban Kerja (Workload Deployment)

BAB 5: PENGUJIAN DAN BUKTI INTEGRASI
5.1 Bukti Integrasi Single Sign-On (SSO) dan Validasi Token JWT
5.2 Bukti Implementasi Read/Write Splitting
5.3 Bukti Persistensi Data (Failover dan Self-Healing StatefulSet)

BAB 6: KESIMPULAN

================================================================================

BAB 1: PENDAHULUAN

1.1 Latar Belakang
Dalam perkembangan industri perangkat lunak modern, kebutuhan terhadap keandalan data (data reliability), ketersediaan tinggi (high availability), dan kinerja transaksi yang cepat menjadi pilar utama sistem tingkat enterprise. Pendekatan arsitektur basis data monolitik tunggal (single instance database) memiliki kelemahan mendasar berupa adanya titik kegagalan tunggal (single point of failure). Beban kueri baca (read) dan transaksi tulis (write) yang terpusat pada satu peladen sering kali memicu kemacetan sistem (bottleneck) dan menyebabkan sistem berhenti bekerja (downtime).

Untuk mengatasi kendala tersebut, arsitektur basis data modern menerapkan konsep Basis Data Terdistribusi menggunakan mekanisme Replikasi Streaming (Streaming Replication) dengan model Primary-Replica. Dalam pola ini, transaksi pengubahan data dialokasikan secara eksklusif ke simpul Primary, sementara transaksi pembacaan dan analisis data dialihkan ke satu atau lebih simpul Replica. Teknik pemisahan beban ini dikenal sebagai Read/Write Splitting.

Di era komputasi awan dan metode DevOps saat ini, deployment sistem terdistribusi dipermudah dan distandarisasi menggunakan teknologi kontainerisasi Docker serta platform orkestrasi Kubernetes. Melalui Kubernetes, simpul-simpul basis data dapat dikelola secara otomatis menggunakan StatefulSet yang menjamin kestabilan identitas jaringan dan persistensi volume data melalui PersistentVolumeClaim (PVC). Selain keandalan data dan infrastruktur, keamanan antarmuka program aplikasi (API) dilindungi menggunakan sistem Single Sign-On (SSO) berbasis Keycloak dan protokol JSON Web Token (JWT) untuk mengontrol hak akses pengguna secara tersentralisasi.


1.2 Rumusan Masalah dan Tujuan
Tujuan pelaksanaan proyek Ujian Tengah Semester (UTS) ini adalah:
1. Membangun infrastruktur replikasi basis data PostgreSQL terdistribusi model Primary-Replica secara otomatis.
2. Mengembangkan antarmuka Backend API berbasis Python FastAPI dengan arsitektur multi-engine untuk pemisahan kueri baca dan tulis (Read/Write Splitting).
3. Menerapkan mekanisme pengamanan API berbasis otentikasi Bearer Token JWT yang terintegrasi dengan Keycloak SSO.
4. Melakukan kontainerisasi aplikasi secara efisien dan aman menggunakan Dockerfile Multi-Stage serta orkestrasi Docker Compose.
5. Melakukan orkestrasi tingkat lanjut ke klaster Kubernetes (Minikube) menggunakan StatefulSet, Headless Service, PersistentVolumeClaim, ConfigMap, dan Secret.
6. Membuktikan keandalan sistem melalui serangkaian pengujian terukur, meliputi validasi token SSO, pemisahan rute database, serta persistensi data saat pod mengalami kegagalan.

================================================================================

BAB 2: ARSITEKTUR SISTEM DAN TOPOLOGI

2.1 Deskripsi Komponen Sistem
Arsitektur sistem yang dibangun terdiri dari empat komponen utama yang bekerja secara terkoordinasi:

1. PostgreSQL Primary (db-primary)
Merupakan simpul utama yang bertanggung jawab menerima dan memproses seluruh operasi penulisan data (INSERT, UPDATE, DELETE). Simpul ini dikonfigurasi dengan Write-Ahead Logging (WAL) pada level replica, membuat slot replikasi, dan mengalirkan rekaman transaksi ke simpul replika secara berkesinambungan.

2. PostgreSQL Replica (db-replica)
Merupakan simpul sekunder yang beroperasi dalam mode hanya-baca (read-only standby). Simpul ini dibangun dari cadangan fisik simpul utama (pg_basebackup) dan secara terus-menerus menyinkronkan data melalui replikasi streaming. Simpul replika ditujukan khusus melayani permintaan pembacaan data (SELECT).

3. Keycloak SSO Server (keycloak)
Merupakan peladen manajemen identitas dan otentikasi terpusat (Identity and Access Management). Keycloak menerbitkan token identitas digital berbasis JSON Web Token (JWT) yang wajib disertakan oleh pengguna saat mengakses fungsi bisnis API.

4. FastAPI Backend Application (backend-api)
Merupakan peladen API berbasis Python 3.11 asinkron. Backend ini mengelola dua koneksi SQLAlchemy terpisah, yaitu engine_primary untuk kueri tulis dan engine_replica untuk kueri baca, serta bertugas memvalidasi keabsahan token JWT pada setiap permintaan yang masuk.


2.2 Alur dan Topologi Sistem
Alur komunikasi dan perpindahan data pada sistem ini dirancang dengan tahapan terstruktur sebagai berikut:

Tahap 1: Pengguna melakukan proses login ke Keycloak SSO dengan memasukkan kredensial yang valid.
Tahap 2: Keycloak memvalidasi identitas pengguna dan menerbitkan Bearer Token berupa JWT.
Tahap 3: Pengguna mengirimkan permintaan HTTP ke FastAPI Backend API dengan menyertakan header Authorization: Bearer <token>.
Tahap 4: FastAPI memvalidasi integritas, masa berlaku, dan klaim subject (sub) pada token JWT.
Tahap 5: Jika token terbukti sah, permintaan diarahkan sesuai jenis operasinya:
- Apabila berupa permintaan tulis (POST /predict), sistem menggunakan engine_primary dan menulis data ke PostgreSQL Primary.
- Apabila berupa permintaan baca (GET /history), sistem menggunakan engine_replica dan mengambil data dari PostgreSQL Replica.
- Apabila berupa pemantauan kesehatan (GET /health), sistem melakukan ping koneksi ke kedua simpul database secara serentak.
Tahap 6: PostgreSQL Primary secara otomatis mereplikasi data mutasi terbaru ke PostgreSQL Replica melalui protokol WAL Streaming Replication.


2.3 Mekanisme Pemisahan Baca dan Tulis (Read/Write Splitting)
Logika pemisahan baca dan tulis diimplementasikan langsung pada lapisan kode aplikasi menggunakan pola Dependency Injection di FastAPI:
1. Fungsi get_primary_db() menyediakan sesi transaksi yang terhubung ke host db-primary port 5432. Fungsi ini diinjeksi pada endpoint POST /predict.
2. Fungsi get_replica_db() menyediakan sesi transaksi yang terhubung ke host db-replica port 5432. Fungsi ini diinjeksi pada endpoint GET /history.
3. Struktur respons API secara transparan menampilkan atribut written_to: primary pada operasi penulisan dan read_from: replica pada operasi pembacaan untuk memudahkan verifikasi rute kueri.

================================================================================

BAB 3: TAHAP 1 - KONTAINERISASI DOCKER

3.1 Perancangan Dockerfile Multi-Stage
Untuk memastikan performa dan keamanan optimal, berkas Dockerfile dibangun dengan konsep Multi-Stage Build yang terdiri dari dua tahapan:

1. Stage 1 (Builder):
Menggunakan citra dasar python:3.11-slim. Pada tahap ini dipasang perkakas kompilasi sistem seperti gcc dan libpq-dev. Virtual environment (/opt/venv) dibuat untuk mengompilasi dan memasang seluruh dependensi pustaka Python dari requirements.txt (fastapi, uvicorn, sqlalchemy, psycopg2-binary, psycopg[binary], python-jose, dan requests).

2. Stage 2 (Runner):
Menggunakan citra dasar python:3.11-slim yang baru dan bersih. Hanya pustaka runtime libpq5 dan curl yang dipasang pada tahap ini. Direktori virtual environment yang sudah siap pakai disalin dari Stage Builder. Seluruh perkakas compiler gcc dibuang sehingga ukuran image menjadi sangat kecil. Eksekusi aplikasi dijalankan oleh pengguna non-root (appuser) demi memenuhi kaidah keamanan kontainer.


3.2 Orkestrasi Layanan dengan Docker Compose
Berkas docker-compose.yml mengelola keempat layanan kontainer di dalam sebuah jaringan terisolasi (sbd-network):
1. db-primary: Menjalankan skrip inisialisasi /postgres/primary/init.sh untuk mendefinisikan user replikator dan parameter WAL.
2. db-replica: Menjalankan skrip kustom /postgres/replica/entrypoint.sh yang menunggu kesiapan primary, melakukan kloning data dengan pg_basebackup -R, mengaktifkan standby.signal, dan menjalankan server postgres menggunakan user aman postgres via gosu.
3. keycloak: Dijalankan dengan perintah start-dev pada port 8080.
4. backend-api: Membaca variabel koneksi database dan Keycloak secara dinamis dengan pengaturan depends_on yang memastikan kedua simpul database sudah sehat sebelum API menerima permintaan.


3.3 Bukti Eksekusi Kontainer Docker

A. Eksekusi Perintah Docker Compose Up
Pada tahap ini dijalankan perintah pembangunan citra dan pengaktifan seluruh kontainer di latar belakang.

[Sisipkan Screenshot terminal eksekusi perintah: docker compose up -d --build di sini]
Gambar 3.1: Tangkapan Layar Eksekusi Perintah docker compose up -d --build


B. Pemeriksaan Status Kontainer (Docker Compose PS)
Hasil verifikasi menunjukkan bahwa keempat kontainer (db-primary, db-replica, keycloak, dan backend-api) berjalan secara simultan dan berada dalam status Up (healthy).

[Sisipkan Screenshot terminal eksekusi perintah: docker compose ps di sini]
Gambar 3.2: Tangkapan Layar Status Seluruh Layanan pada docker compose ps

================================================================================

BAB 4: TAHAP 2 - ORKESTRASI KUBERNETES (MINIKUBE)

4.1 Peran StatefulSet dalam Basis Data Terdistribusi
Berbeda dengan komponen aplikasi tanpa status (stateless) seperti backend-api yang menggunakan Deployment, simpul basis data terdistribusi memerlukan identitas simpul yang persisten dan terurut. Oleh karena itu, PostgreSQL Primary dan Replica diimplementasikan menggunakan StatefulSet pada Kubernetes.

Setiap simpul StatefulSet dilengkapi dengan Headless Service (clusterIP: None) bernama db-primary-headless dan db-replica-headless. Fitur ini memungkinkan pod ditemukan secara langsung oleh sistem replikasi melalui nama domain internal Kubernetes (DNS internal) tanpa mengalami pengacakan routing. Selain itu, disediakan Service ClusterIP reguler (db-primary dan db-replica) agar backend API dapat terhubung ke basis data melalui nama host yang stabil.


4.2 Manajemen Persistensi dengan PersistentVolumeClaim (PVC)
Untuk mencegah hilangnya data ketika sebuah pod mengalami terminasi, dibuat mekanisme alokasi penyimpanan otomatis menggunakan volumeClaimTemplates pada manifest StatefulSet:
1. Kubernetes secara otomatis mengaitkan sebuah PersistentVolumeClaim (PVC) berkapasitas 1 GiB dengan mode akses ReadWriteOnce untuk masing-masing pod database.
2. Direktori data diikat pada folder /var/lib/postgresql/data/pgdata. Penggunaan subfolder pgdata ini mencegah terjadinya galat saat direktori bawaan sistem berkas Linux (lost+found) terdeteksi.
3. Apabila pod mengalami gangguan atau dihapus, disk penyimpanan fisik tidak dihapus dan akan segera dipasangkan kembali ke pod yang baru dibuat.


4.3 Pemisahan Konfigurasi dan Kredensial (ConfigMap dan Secret)
Sesuai dengan metodologi Cloud-Native Twelve-Factor App, seluruh konfigurasi dan data kredensial dipisahkan secara tegas dari kode program:
1. Berkas k8s/secret.yaml (app-secret):
Menyimpan data sensitif yang dienkripsi berupa POSTGRES_PASSWORD, REPLICATION_PASSWORD, KEYCLOAK_ADMIN_PASSWORD, dan SECRET_KEY aplikasi.
2. Berkas k8s/configmap.yaml (app-config, postgres-primary-init, postgres-replica-init):
Menyimpan konfigurasi lingkungan non-sensitif seperti nama database, nomor port, nama service (DB_HOST: db-primary dan REPLICA_DB_HOST: db-replica), konfigurasi Keycloak, serta skrip inisialisasi basis data (init.sh dan entrypoint.sh).


4.4 Status Penyebaran Beban Kerja (Workload Deployment)
Setelah seluruh manifest diaplikasikan ke Minikube menggunakan perintah kubectl apply -f k8s/, seluruh beban kerja berhasil dialokasikan secara harmonis.

[Sisipkan Screenshot terminal hasil eksekusi: kubectl get pods, kubectl get svc, dan kubectl get pvc di sini]
Gambar 4.1: Tangkapan Layar Status Pod, Service, dan PersistentVolumeClaim pada Kubernetes

================================================================================

BAB 5: PENGUJIAN DAN BUKTI INTEGRASI

5.1 Bukti Integrasi Single Sign-On (SSO) dan Validasi Token JWT
Lapisan keamanan API mewajibkan penyertaan header Authorization: Bearer <token> pada setiap pemanggilan endpoint transaksi. Apabila permintaan dikirim tanpa token atau menggunakan token yang salah, server FastAPI menolak akses dengan respons HTTP 401 Unauthorized.

Pengujian otentikasi dilakukan dengan menerbitkan token JWT menggunakan skrip Python generate_token.py (atau melalui endpoint token Keycloak). Token yang berisi identitas pengguna kemudian disematkan pada permintaan HTTP. Sistem berhasil memverifikasi token dan mengizinkan eksekusi transaksi.

[Sisipkan Screenshot pembuatan token JWT dan bukti keberhasilan request dengan header Bearer Token di sini]
Gambar 5.1: Tangkapan Layar Pembuatan Token JWT dan Pengujian Request Terotentikasi


5.2 Bukti Implementasi Read/Write Splitting
Pengujian ini bertujuan membuktikan bahwa sistem secara akurat mengarahkan transaksi sesuai perannya tanpa terjadi kesalahan rute:

1. Pengujian Endpoint Pemantauan (GET /health):
Endpoint /health menguji koneksi langsung ke simpul Primary dan Replica secara simultan. Hasil respons JSON menunjukkan bahwa status kedua database terhubung (db_primary: connected dan db_replica: connected).

2. Pengujian Transaksi Tulis (POST /predict):
Klien mengirimkan data prediksi baru dengan menyertakan header otentikasi. Sistem menyimpan entri data ke tabel predictions pada simpul db-primary. Respons JSON mengonfirmasi status keberhasilan dengan keterangan written_to: primary.

3. Pengujian Transaksi Baca (GET /history):
Klien meminta riwayat prediksi yang telah tersimpan. Kueri dijalankan secara khusus ke simpul db-replica. Respons JSON mengembalikan daftar riwayat transaksi dengan keterangan read_from: replica. Hal ini membuktikan bahwa data yang baru saja ditulis ke Primary telah berhasil tersinkronisasi ke Replica dan dibaca dengan lancar.

[Sisipkan Screenshot hasil eksekusi pengujian GET /health, POST /predict, dan GET /history di sini]
Gambar 5.2: Tangkapan Layar Bukti Pengujian Endpoint Read/Write Splitting pada API


5.3 Bukti Persistensi Data (Failover dan Self-Healing StatefulSet)
Pengujian persistensi data dilakukan melalui skenario kegagalan pod (chaos testing) untuk menguji keandalan mekanisme pemulihan mandiri Kubernetes dan kekekalan data pada Persistent Volume Claim:

Tahap 1: Memastikan sejumlah data telah tersimpan di dalam database melalui pengujian endpoint sebelumnya.
Tahap 2: Menghapus pod utama secara paksa dengan mengeksekusi perintah terminal:
kubectl delete pod db-primary-0
Tahap 3: Memantau reaksi klaster Kubernetes. Pengendali StatefulSet mendeteksi hilangnya pod db-primary-0 dan secara otomatis membuat pod pengganti baru dengan nama yang sama persis (db-primary-0) serta langsung mengaitkan kembali PVC data lama.
Tahap 4: Mengakses kembali endpoint GET /history setelah pod kembali berstatus Running. Seluruh rekaman data transaksi yang dibuat sebelum pod dihapus terbukti tetap ada, utuh, dan tidak mengalami kerusakan atau kehilangan data (zero data loss).

[Sisipkan Screenshot terminal saat menghapus pod (kubectl delete pod db-primary-0), status pod kembali Running, dan bukti data tetap utuh saat diakses kembali via GET /history di sini]
Gambar 5.3: Tangkapan Layar Proses Penghapusan Pod Primary, Self-Healing Kubernetes, dan Bukti Persistensi Data

================================================================================

BAB 6: KESIMPULAN

Berdasarkan seluruh tahapan perancangan, implementasi, dan pengujian yang telah diselesaikan pada proyek Ujian Tengah Semester Sistem Basis Data Terdistribusi ini, dapat diambil kesimpulan sebagai berikut:

1. Replikasi Streaming Terotomatisasi: Arsitektur basis data PostgreSQL Primary-Replica berhasil diimplementasikan dengan sinkronisasi data yang cepat dan konsisten melalui pemanfaatan Write-Ahead Logging (WAL).
2. Efisiensi Beban Kerja Melalui Read/Write Splitting: Pembagian tugas pada level aplikasi terbukti sukses mendistribusikan beban transaksi, di mana mutasi data dialokasikan ke Primary dan kueri pembacaan dilayani oleh Replica, sehingga memperkecil risiko kemacetan sistem.
3. Keandalan Tinggi Berbasis Kubernetes StatefulSet: Penerapan StatefulSet yang dikombinasikan dengan PersistentVolumeClaim (PVC) pada Minikube menjamin persistensi data tingkat tinggi. Uji penghapusan pod membuktikan bahwa mekanisme pemulihan mandiri (self-healing) Kubernetes mampu mengembalikan ketersediaan layanan tanpa kehilangan data sedikit pun.
4. Pengamanan Sistem Terpusat: Integrasi autentikasi berbasis Single Sign-On (SSO) dan token digital JWT memberikan lapisan proteksi yang andal terhadap akses antarmuka API dan aset basis data terdistribusi.
5. Standardisasi Kontainer Cloud-Native: Penggunaan Dockerfile Multi-Stage serta pemisahan konfigurasi melalui ConfigMap dan Secret menghasilkan arsitektur perangkat lunak yang aman, berukuran ringan, modular, serta memenuhi kaidah sistem modern siap pakai (production-ready).
