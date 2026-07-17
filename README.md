# Trading Edge Intelligence System (TEIS)

**Trading Edge Intelligence System (TEIS)** adalah platform pencatatan trading personal (journaling) & analisa edge trading crypto berbasis data dengan single-user flow. Aplikasi ini dirancang khusus untuk mengukur, memvalidasi, dan menjaga edge trading pribadi berbasis data, bukan asumsi, untuk manual trading crypto futures (didukung untuk Binance Futures USDT-M).

Platform ini mengintegrasikan pencatatan subjektif cepat (Quick-Tag Capture) dengan data objektif pasar secara real-time melalui Binance API Sync, serta menganalisa kinerja menggunakan model statistik.

---

## 🛠️ Tech Stack & Arsitektur

TEIS dibangun dengan arsitektur monorepo modular-monolith:
- **Backend (Python 3.12)**: FastAPI, Uvicorn, Celery (background tasks), Redis (broker), SQLAlchemy 2.0 (ORM), Alembic (DB migrations).
- **Analitik & Statistik**: pandas, NumPy, SciPy, statsmodels.
- **Database**: MySQL 8.0 (konfigurasi character set `utf8mb4`).
- **Object Storage**: MinIO (S3-compatible) untuk screenshot chart trade secara lokal.
- **Frontend**: React + Vite (Quick-Tag Capture PWA dengan IndexedDB offline-first).
- **Infrastruktur**: Docker Compose untuk deployment lokal terpadu.

---

## 📁 Struktur Direktori

```text
teis/
├── .env                  # Environment variables (lokal, jangan masuk git)
├── .env.example          # Template variabel lingkungan
├── .gitignore            # Konfigurasi pengecualian git
├── docker-compose.yml    # Konfigurasi container orkestrasi lokal
├── README.md             # Dokumentasi utama proyek
│
├── backend/
│   ├── alembic/          # File migrasi database
│   │   ├── versions/     # Kumpulan file script migrasi (001_initial_migration.py)
│   │   └── env.py
│   ├── app/              # Source code utama FastAPI
│   │   ├── api/          # Route/Endpoint API
│   │   ├── models/       # Definisi model database SQLAlchemy
│   │   ├── schemas/      # Validasi skema input/output Pydantic
│   │   ├── tasks/        # Celery worker & background tasks
│   │   ├── config.py     # Loader environment variables
│   │   ├── database.py   # Setup engine & session database
│   │   └── main.py       # Entry point aplikasi backend
│   ├── Dockerfile
│   └── requirements.txt  # Daftar dependensi Python
│
└── frontend/             # Aplikasi frontend (React PWA)
    ├── src/
    ├── Dockerfile
    ├── package.json
    └── vite.config.js
```

---

## 🚀 Panduan Memulai di Lokal

### Prasyarat
Pastikan Anda sudah menginstal:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Git](https://git-scm.com/)

### Langkah 1: Kloning & Persiapan Env
1. Duplikat file `.env.example` menjadi `.env` di direktori root:
   ```bash
   cp .env.example .env
   ```
2. Sesuaikan nilai di dalam `.env` jika diperlukan (secara default sudah dikonfigurasi siap jalan untuk lokal).

### Langkah 2: Menjalankan Docker Compose
Jalankan semua layanan lokal secara background menggunakan perintah:
```bash
docker-compose up --build -d
```
Perintah ini akan menyalakan dan membangun container untuk:
1. **MySQL 8** (Port `3306`)
2. **Redis** (Port `6379`)
3. **MinIO** (API port `9000`, Console port `9001`)
4. **FastAPI Backend** (Port `8000`)
5. **Celery Worker** (Background worker)
6. **MinIO Init** (Otomatis membuat bucket `teis-screenshots`)
7. **React Frontend** (Port `5173`)

### Langkah 3: Menjalankan Migrasi Database
Setelah kontainer database aktif, masuk ke kontainer backend untuk mengaplikasikan skema awal database melalui Alembic:
```bash
docker-compose exec backend alembic upgrade head
```

---

## 🔗 Akses Port Layanan Lokal

- **Frontend React**: [http://localhost:5173](http://localhost:5173)
- **FastAPI Docs (API)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001)
  - *Username*: `teis_minio_admin`
  - *Password*: `teis_minio_secret_pass`

---

## 📤 Unggah Proyek ke GitHub

Ikuti langkah-langkah di bawah untuk mengunggah setup proyek ini ke GitHub baru Anda:

1. Buat repositori baru kosong di GitHub Anda (jangan centang opsi *Add a README*, *Add .gitignore*, atau *Choose a license*).
2. Salin URL repositori Anda, misalnya: `https://github.com/username/teis.git`.
3. Buka terminal di direktori root `teis` lokal Anda dan jalankan perintah berikut:
   ```bash
   # Menghubungkan remote GitHub ke proyek lokal Anda
   git remote add origin https://github.com/username/teis.git

   # Mengubah nama branch utama menjadi main jika belum
   git branch -M main

   # Melakukan track pada seluruh setup awal
   git add .

   # Membuat commit pertama
   git commit -m "feat: setup awal proyek TEIS (FastAPI, React PWA, Docker, DB Schema v1.1)"

   # Push proyek ke GitHub
   git push -u origin main
   ```
