"""
School Device Monitor - Admin Server
-------------------------------------
Receives violation reports from client agents and shows them in a simple
web dashboard for school admins/IT staff.

Run:
    pip install flask
    python app.py
Then visit http://localhost:5000/admin (default login: admin / changeme)
"""

import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "CHANGE-THIS-TO-A-RANDOM-SECRET-IN-PRODUCTION"

DB_PATH = Path(__file__).parent / "monitor.db"

# --- change these before deploying ---
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "changeme"
# --------------------------------------


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            username TEXT,
            category TEXT,
            matched_on TEXT,
            matched_value TEXT,
            window_title TEXT,
            timestamp TEXT,
            received_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/api/alert", methods=["POST"])
def receive_alert():
    data = request.get_json(force=True, silent=True) or {}
    required = ["device_id", "username", "category", "matched_on", "matched_value", "window_title", "timestamp"]
    if not all(k in data for k in required):
        return jsonify({"error": "missing fields"}), 400

    conn = get_db()
    conn.execute(
        """
        INSERT INTO alerts (device_id, username, category, matched_on, matched_value, window_title, timestamp, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["device_id"], data["username"], data["category"],
            data["matched_on"], data["matched_value"], data["window_title"],
            data["timestamp"], datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "received"}), 201


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin"))
        error = "Invalid credentials"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@login_required
def admin():
    conn = get_db()

    student_filter = request.args.get("student", "").strip()
    category_filter = request.args.get("category", "").strip()

    query = "SELECT * FROM alerts WHERE 1=1"
    params = []
    if student_filter:
        query += " AND username LIKE ?"
        params.append(f"%{student_filter}%")
    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)
    query += " ORDER BY received_at DESC LIMIT 500"

    alerts = conn.execute(query, params).fetchall()

    summary = conn.execute(
        "SELECT username, COUNT(*) as cnt FROM alerts GROUP BY username ORDER BY cnt DESC LIMIT 10"
    ).fetchall()

    conn.close()
    return render_template(
        "admin.html", alerts=alerts, summary=summary,
        student_filter=student_filter, category_filter=category_filter,
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
