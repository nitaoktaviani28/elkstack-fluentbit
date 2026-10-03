# Image dasar: Python 3.12 versi "slim" (ringan, tapi tetap Debian
# sehingga psycopg2-binary bisa langsung terpasang tanpa compile).
FROM python:3.12-slim

# Folder kerja di dalam container. Semua perintah & path relatif
# setelah ini dijalankan dari /app.
WORKDIR /app

# Salin HANYA requirements.txt dulu (sebelum kode aplikasi).
# Tujuannya: memanfaatkan cache Docker selama requirements tidak
# berubah, langkah install di bawah tidak perlu diulang saat rebuild.
COPY requirements.txt .

# Install dependency Python (Flask, psycopg2-binary).
# --no-cache-dir: jangan simpan cache pip -> ukuran image lebih kecil.
RUN pip install --no-cache-dir -r requirements.txt

# Salin sisa kode aplikasi (app.py, db.py, templates/, static/) ke /app.
COPY . .

# Dokumentasi bahwa aplikasi berjalan di port 8080 (sifatnya informatif;
# pemetaan port sebenarnya diatur di docker-compose.yml).
EXPOSE 8080

# Perintah default saat container dijalankan: start aplikasi Flask.
CMD ["python", "app.py"]
