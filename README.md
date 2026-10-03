# 💊 Apotek Sehat

Aplikasi web apotek sederhana (Flask + PostgreSQL) dengan **signup**, **login**,
dan **dashboard katalog obat**. Semua aktivitas dicatat sebagai **log JSON** dan
dikirim ke Elasticsearch lewat **Fluent Bit** untuk centralized logging.

## Teknologi
- Backend: Python Flask
- Database: PostgreSQL (password ter-hash, data obat di-seed otomatis)
- Logging: stdout JSON → Fluent Bit → Elasticsearch (index `app-logs`)

## Menjalankan
```bash
# Build image dan jalankan seluruh stack di background
docker compose up -d --build

# Lihat status service
docker compose ps

# Pantau log aplikasi
docker compose logs -f app
```
Buka http://localhost:8080 → Sign Up → Login → Dashboard.

### Command Docker yang berguna
```bash
# Validasi konfigurasi Compose tanpa menjalankan container
docker compose config

# Lihat status health aplikasi
docker inspect --format='{{.State.Health.Status}}' apotek-app

# Cek endpoint health dari host
curl http://localhost:8080/healthz

# Restart aplikasi setelah perubahan konfigurasi
docker compose restart app

# Hentikan stack tanpa menghapus volume database
docker compose down

# Hentikan stack sekaligus hapus data PostgreSQL
docker compose down -v
```

## Konfigurasi (environment variable)
| Variabel | Default | Keterangan |
|---|---|---|
| `DB_HOST` | `postgres` | host database |
| `DB_PORT` | `5432` | port database |
| `DB_NAME` | `apotek` | nama database |
| `DB_USER` | `apotek_user` | user database |
| `DB_PASSWORD` | `apotek_pass` | password database |
| `SERVICE_NAME` | `apotek-app` | nama service di log |
| `SECRET_KEY` | `rahasia-lab-elk` | kunci session Flask |

## Endpoint
| Method | Path | Keterangan |
|---|---|---|
| GET | `/` | redirect ke login/dashboard |
| GET/POST | `/signup` | registrasi akun |
| GET/POST | `/login` | login |
| GET | `/logout` | logout |
| GET | `/dashboard` | katalog obat (perlu login) |
| GET | `/healthz` | health check |

## Menghentikan
```bash
docker compose down        # hentikan
docker compose down -v     # + hapus data PostgreSQL
```
