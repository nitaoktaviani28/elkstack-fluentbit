import json
import logging
import os
import random
import socket
import threading
import time
from collections import deque
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string, request

# ------------------------------------------------------------------
# Konfigurasi via environment variable
# ------------------------------------------------------------------
SERVICE_NAME = os.getenv("SERVICE_NAME", "auth-service")
# DB_HOST sengaja KOSONG di Lab 2 (aplikasi sehat).
# Di Lab 3 kita isi dengan host ngaco -> memicu "Database connection failed".
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

# Penyimpanan log terakhir + statistik (untuk ditampilkan di UI)
RECENT_LOGS = deque(maxlen=200)
STATS = {"total": 0, "info": 0, "warning": 0, "error": 0}
_lock = threading.Lock()

# ------------------------------------------------------------------
# Logging: semua log keluar sebagai JSON (satu baris = satu event)
# supaya gampang di-parse Fluent Bit lalu masuk Elasticsearch.
# ------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "message": record.getMessage(),
        }
        return json.dumps(payload)

class UIBufferHandler(logging.Handler):
    """Simpan log ke memori supaya bisa ditampilkan di live feed UI."""

    def emit(self, record):
        with _lock:
            level = record.levelname
            RECENT_LOGS.appendleft(
                {
                    "ts": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "level": level,
                    "message": record.getMessage(),
                }
            )
            STATS["total"] += 1
            STATS[level.lower()] = STATS.get(level.lower(), 0) + 1

_stream = logging.StreamHandler()
_stream.setFormatter(JsonFormatter())
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.handlers = [_stream, UIBufferHandler()]
logging.getLogger("werkzeug").setLevel(logging.WARNING)

log = logging.getLogger(SERVICE_NAME)
app = Flask(__name__)

def check_db():
    """Cek koneksi ke 'database'. DB_HOST kosong = dianggap sehat.
    DB_HOST diisi tapi tidak terjangkau -> log ERROR."""
    if not DB_HOST:
        return True
    try:
        with socket.create_connection((DB_HOST, DB_PORT), timeout=2):
            return True
    except Exception as e:
        log.error(
            f"Database connection failed: cannot reach {DB_HOST}:{DB_PORT} ({e})"
        )
        return False

# ------------------------------------------------------------------
# UI
# ------------------------------------------------------------------
INDEX_HTML = """
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ service }} — Demo App</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --muted:#94a3b8; --line:#334155;
          --info:#38bdf8; --warn:#fbbf24; --err:#f87171; --ok:#34d399; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:#e2e8f0; }
  header { padding:20px 24px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:12px; }
  header h1 { font-size:18px; margin:0; }
  .dot { width:10px; height:10px; border-radius:50%; background:var(--ok);
         box-shadow:0 0 10px var(--ok); }
  .wrap { max-width:1000px; margin:0 auto; padding:24px; }
  .stats { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }
  .stat { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; }
  .stat .n { font-size:26px; font-weight:700; }
  .stat .l { font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
  .buttons { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:20px; }
  button { cursor:pointer; border:none; border-radius:10px; padding:14px 16px;
           font-size:14px; font-weight:600; color:#0f172a; transition:transform .05s; }
  button:active { transform:scale(.97); }
  .b-ok   { background:var(--ok); }
  .b-info { background:var(--info); }
  .b-warn { background:var(--warn); }
  .b-err  { background:var(--err); }
  .b-burst{ background:#a78bfa; }
  .console { background:#020617; border:1px solid var(--line); border-radius:12px;
             height:360px; overflow-y:auto; padding:14px; font-family:ui-monospace,Menlo,Consolas,monospace;
             font-size:13px; line-height:1.7; }
  .row { white-space:pre-wrap; }
  .lvl { font-weight:700; }
  .INFO .lvl{color:var(--info);} .WARNING .lvl{color:var(--warn);}
  .ERROR .lvl{color:var(--err);} .time{color:var(--muted);}
  h2 { font-size:14px; color:var(--muted); margin:0 0 10px; text-transform:uppercase; letter-spacing:.5px; }
</style>
</head>
<body>
  <header>
    <span class="dot"></span>
    <h1>{{ service }}</h1>
    <span style="color:var(--muted);font-size:13px;">— demo application for centralized logging</span>
  </header>
  <div class="wrap">
    <div class="stats">
      <div class="stat"><div class="n" id="s-total">0</div><div class="l">Total</div></div>
      <div class="stat"><div class="n" style="color:var(--info)" id="s-info">0</div><div class="l">Info</div></div>
      <div class="stat"><div class="n" style="color:var(--warn)" id="s-warning">0</div><div class="l">Warning</div></div>
      <div class="stat"><div class="n" style="color:var(--err)" id="s-error">0</div><div class="l">Error</div></div>
    </div>

    <h2>Aksi (klik untuk menghasilkan log)</h2>
    <div class="buttons">
      <button class="b-ok"    onclick="hit('/api/login')">🔐 Login</button>
      <button class="b-info"  onclick="hit('/api/health')">❤️ Health Check</button>
      <button class="b-warn"  onclick="hit('/api/slow')">🐌 Slow Request</button>
      <button class="b-err"   onclick="hit('/api/error')">💥 Trigger Error</button>
      <button class="b-burst" onclick="hit('/api/burst?n=10')">⚡ Burst x10</button>
    </div>

    <h2>Live log feed</h2>
    <div class="console" id="console"></div>
  </div>

<script>
async function hit(url){ try { await fetch(url, {method:'POST'}); } catch(e){} refresh(); }
async function refresh(){
  try {
    const [logs, stats] = await Promise.all([
      fetch('/api/logs').then(r=>r.json()),
      fetch('/api/stats').then(r=>r.json())
    ]);
    s('s-total',stats.total); s('s-info',stats.info);
    s('s-warning',stats.warning); s('s-error',stats.error);
    document.getElementById('console').innerHTML = logs.map(l =>
      `<div class="row ${l.level}"><span class="time">${l.ts}</span> `+
      `<span class="lvl">${l.level.padEnd(7)}</span> ${esc(l.message)}</div>`
    ).join('');
  } catch(e){}
}
function s(id,v){ document.getElementById(id).textContent=v; }
function esc(t){ return (t||'').replace(/[&<>]/g, c=>({'&':'&','<':'<','>':'>'}[c])); }
setInterval(refresh, 2000); refresh();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, service=SERVICE_NAME)

@app.route("/api/logs")
def api_logs():
    with _lock:
        return jsonify(list(RECENT_LOGS))

@app.route("/api/stats")
def api_stats():
    with _lock:
        return jsonify(dict(STATS))

# ------------------------------------------------------------------
# Aksi (menghasilkan log) — dipanggil dari tombol UI atau curl
# ------------------------------------------------------------------
@app.route("/api/health", methods=["GET", "POST"])
def health():
    if check_db():
        log.info("Health check passed")
        return jsonify(status="healthy"), 200
    log.warning("Health check degraded: database unreachable")
    return jsonify(status="degraded"), 503

@app.route("/api/login", methods=["GET", "POST"])
def login():
    user = random.choice(["alice", "bob", "charlie"])
    if not check_db():
        log.error(f"Login failed for user={user}: database connection error - HTTP 500")
        return jsonify(error="internal server error"), 500
    log.info(f"User {user} logged in successfully - 200 OK")
    return jsonify(status="logged_in", user=user)

@app.route("/api/error", methods=["GET", "POST"])
def error():
    log.error("Unhandled exception while processing request - HTTP 500")
    return jsonify(error="internal server error"), 500

@app.route("/api/slow", methods=["GET", "POST"])
def slow():
    delay = random.uniform(2, 5)
    log.warning(f"Slow response detected: took {delay:.1f}s")
    time.sleep(delay)
    return jsonify(status="ok", delay=round(delay, 1))

@app.route("/api/burst", methods=["GET", "POST"])
def burst():
    n = min(int(request.args.get("n", 10)), 50)
    for _ in range(n):
        roll = random.random()
        if roll < 0.2:
            log.error("Unhandled exception while processing request - HTTP 500")
        elif roll < 0.35:
            log.warning("High response time detected")
        else:
            log.info("Request handled /api - 200 OK")
    return jsonify(generated=n)

# ------------------------------------------------------------------
# Generator trafik background: log mengalir terus
# ------------------------------------------------------------------
def background_traffic():
    paths = ["/", "/health", "/login", "/products", "/cart"]
    while True:
        path = random.choice(paths)
        roll = random.random()
        if roll < 0.15:
            check_db()
        elif roll < 0.25:
            log.warning(f"High response time on {path}")
        else:
            log.info(f"Request handled {path} - 200 OK")
        time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    log.info(f"Starting {SERVICE_NAME} ...")
    threading.Thread(target=background_traffic, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
