import json
import logging
import os
import re
import threading
from datetime import datetime, timezone

from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db

SERVICE_NAME = os.getenv("SERVICE_NAME", "apotek-app")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "message": record.getMessage(),
        }
        return json.dumps(payload)

_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.handlers = [_handler]
logging.getLogger("werkzeug").setLevel(logging.WARNING)

log = logging.getLogger(SERVICE_NAME)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        log.info(f"Signup attempt for email={email}")

        if not name or not EMAIL_RE.match(email) or len(password) < 6:
            log.warning(f"Signup failed for email={email}: invalid input")
            flash("Nama wajib, email harus valid, password minimal 6 karakter.", "error")
            return render_template("signup.html"), 400

        try:
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email=%s;", (email,))
            if cur.fetchone():
                cur.close()
                conn.close()
                log.warning(f"Signup failed for email={email}: email already registered")
                flash("Email sudah terdaftar. Silakan login.", "error")
                return render_template("signup.html"), 409

            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s);",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            log.error(f"Signup failed for email={email}: database error - {e}")
            flash("Terjadi kesalahan sistem. Coba lagi nanti.", "error")
            return render_template("signup.html"), 500

        log.info(f"New user registered successfully: email={email}")
        flash("Pendaftaran berhasil! Silakan login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        log.info(f"Login attempt for email={email}")

        try:
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE email=%s;", (email,))
            user = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            # Inilah yang muncul di Lab 3 kalau user/password DB salah:
            # "password authentication failed for user ..."
            log.error(f"Login failed for email={email}: database error - {e}")
            flash("Terjadi kesalahan sistem. Coba lagi nanti.", "error")
            return render_template("login.html"), 500

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = {"name": user["name"], "email": user["email"]}
            log.info(f"User {email} logged in successfully")
            return redirect(url_for("dashboard"))

        log.warning(f"Login failed for email={email}: invalid credentials")
        flash("Email atau password salah.", "error")
        return render_template("login.html"), 401

    return render_template("login.html")

@app.route("/logout")
def logout():
    user = session.get("user", {}).get("email", "unknown")
    session.clear()
    log.info(f"User {user} logged out")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM products ORDER BY name;")
        products = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        log.error(f"Dashboard failed to load products: database error - {e}")
        products = []
        flash("Gagal memuat data obat.", "error")
    log.info(f"Dashboard viewed by {session['user']['email']} ({len(products)} products)")
    return render_template("dashboard.html", user=session["user"], products=products)

@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    log.info(f"Starting {SERVICE_NAME} ...")
    threading.Thread(target=db.init_db, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
