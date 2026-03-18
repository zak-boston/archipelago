"""
Archipelago — backend
======================
Endpoints:
  GET  /                 →  frontend (requires auth)
  GET  /login            →  login page
  POST /login            →  process login
  GET  /logout           →  clear session
  GET  /api/machines     →  load saved machines list
  POST /api/machines     →  save machines list
  POST /api/wake         →  send WOL magic packet
  POST /api/ping         →  check if a machine is reachable
  POST /api/sleep        →  shut a machine down over SSH
  POST /api/reboot       →  reboot a machine over SSH

Requirements:
  pip install flask wakeonlan

Password:
  Set the ARCHIPELAGO_PASSWORD environment variable before running.
  In docker-compose.yml add:
      environment:
        - ARCHIPELAGO_PASSWORD=your_password_here

  If the variable is not set, the app will refuse to start.
"""

import json
import os
import socket
import subprocess
import time
from flask import (Flask, request, jsonify, send_from_directory,
                   session, redirect, url_for, render_template_string)
from wakeonlan import send_magic_packet

app = Flask(__name__, static_folder="static")

# ── Config ────────────────────────────────────────────────────────

PORT = 5000

SSH_USER = "your_ssh_username"

PING_TIMEOUT = 2.0

CHECK_PORTS = [22, 80, 443]

MACHINES_FILE = "/data/machines.json"

# Password comes from environment — never hardcode it
PASSWORD = os.environ.get("ARCHIPELAGO_PASSWORD", "")
if not PASSWORD:
    raise RuntimeError(
        "ARCHIPELAGO_PASSWORD environment variable is not set. "
        "Add it to docker-compose.yml under 'environment'."
    )

# Flask needs a secret key to sign session cookies
app.secret_key = os.environ.get("ARCHIPELAGO_SECRET", os.urandom(24))


# ── Auth ──────────────────────────────────────────────────────────

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🏝️ Archipelago — Login</title>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@700;800;900&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Nunito', sans-serif;
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: linear-gradient(180deg, #c8e8f8 0%, #d8eefc 40%, #e8f5d8 75%, #c8e880 100%);
  }
  .card {
    background: #fffdf7; border: 3px solid #e8d5a0; border-radius: 20px;
    padding: 36px 40px; max-width: 360px; width: 100%;
    box-shadow: 0 6px 0 #d4bc7a, 0 10px 32px rgba(100,80,30,.2);
    text-align: center;
  }
  .sign {
    background: #c8954a; border-radius: 12px 12px 4px 4px;
    padding: 14px 28px 10px; margin: -36px -40px 28px;
    border-bottom: 4px solid #a07030;
  }
  .sign-icon { font-size: 24px; margin-bottom: 4px; }
  .sign-title { font-size: 22px; font-weight: 900; color: #fef9e8;
    text-shadow: 2px 3px 0 rgba(0,0,0,.2); }
  .sign-sub { font-size: 11px; color: #e8d4a0; font-weight: 600; margin-top: 3px; letter-spacing: .08em; }
  label { display: block; font-size: 11px; font-weight: 800; color: #8c7040;
    text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; text-align: left; }
  input[type=password] {
    width: 100%; padding: 10px 14px; border: 2.5px solid #e8d5a0; border-radius: 10px;
    font-family: 'Nunito', sans-serif; font-size: 14px; font-weight: 600;
    background: #fef9f0; color: #5c4a1e; outline: none; margin-bottom: 18px;
    transition: border-color .15s, box-shadow .15s;
  }
  input[type=password]:focus { border-color: #7ec850; box-shadow: 0 0 0 3px rgba(126,200,80,.18); }
  button {
    width: 100%; padding: 12px; border-radius: 14px;
    font-family: 'Nunito', sans-serif; font-size: 14px; font-weight: 900;
    border: 3px solid #5faa30; background: #7ec850; color: white; cursor: pointer;
    box-shadow: 0 4px 0 #5faa30; transition: all .12s;
    text-shadow: 0 1px 2px rgba(0,0,0,.2);
  }
  button:hover { background: #8ad860; transform: translateY(-1px); box-shadow: 0 5px 0 #5faa30; }
  button:active { transform: translateY(2px); box-shadow: 0 2px 0 #5faa30; }
  .error { color: #e05050; font-size: 12px; font-weight: 700; margin-bottom: 14px; }
</style>
</head>
<body>
<div class="card">
  <div class="sign">
    <div class="sign-icon">🏝️</div>
    <div class="sign-title">Archipelago</div>
    <div class="sign-sub">enter your passphrase</div>
  </div>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="POST" action="/login">
    <label>🔑 Password</label>
    <input type="password" name="password" autofocus placeholder="············">
    <button type="submit">🌿 Enter the Island</button>
  </form>
</div>
</body>
</html>"""


@app.before_request
def require_auth():
    """Redirect to login page if not authenticated.
    API endpoints return 401 JSON instead of redirecting."""
    public = {"/login", "/favicon.ico"}
    if request.path in public:
        return None
    if session.get("authed"):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"error": "Unauthorised"}), 401
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["authed"] = True
            return redirect("/")
        return render_template_string(LOGIN_PAGE, error="Wrong password — try again 🌱")
    return render_template_string(LOGIN_PAGE, error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ── Frontend ──────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── Machines persistence ──────────────────────────────────────────

@app.route("/api/machines", methods=["GET"])
def get_machines():
    try:
        if not os.path.exists(MACHINES_FILE):
            return jsonify([])
        with open(MACHINES_FILE, "r") as f:
            return jsonify(json.load(f))
    except Exception as e:
        app.logger.error(f"Failed to load machines: {e}")
        return jsonify([])


@app.route("/api/machines", methods=["POST"])
def save_machines():
    try:
        os.makedirs(os.path.dirname(MACHINES_FILE), exist_ok=True)
        data = request.get_json()
        with open(MACHINES_FILE, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        app.logger.error(f"Failed to save machines: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ── API ───────────────────────────────────────────────────────────

@app.route("/api/ping", methods=["POST"])
def api_ping():
    ip = request.get_json().get("ip", "").strip()
    if not ip:
        return jsonify({"error": "No IP provided"}), 400
    alive, ping_ms = check_host(ip)
    return jsonify({"alive": alive, "ping_ms": ping_ms})


@app.route("/api/wake", methods=["POST"])
def api_wake():
    data = request.get_json()
    mac  = data.get("mac", "").strip()
    ip   = data.get("ip",  "").strip()
    if not mac:
        return jsonify({"ok": False, "error": "No MAC address provided"}), 400
    try:
        broadcast = get_broadcast(ip) if ip else "255.255.255.255"
        send_magic_packet(mac, ip_address=broadcast, port=9)
        app.logger.info(f"WOL packet sent to {mac} via {broadcast}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sleep", methods=["POST"])
def api_sleep():
    ip = request.get_json().get("ip", "").strip()
    if not ip:
        return jsonify({"ok": False, "error": "No IP provided"}), 400
    ok, err = ssh_command(ip, "sudo shutdown -h now")
    return jsonify({"ok": ok, "error": err})


@app.route("/api/reboot", methods=["POST"])
def api_reboot():
    ip = request.get_json().get("ip", "").strip()
    if not ip:
        return jsonify({"ok": False, "error": "No IP provided"}), 400
    ok, err = ssh_command(ip, "sudo shutdown -r now")
    return jsonify({"ok": ok, "error": err})


# ── Helpers ───────────────────────────────────────────────────────

def get_broadcast(ip: str) -> str:
    parts = ip.strip().split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.255"
    return "255.255.255.255"


def check_host(ip: str) -> tuple[bool, int]:
    start = time.time()
    for port in CHECK_PORTS:
        try:
            with socket.create_connection((ip, port), timeout=PING_TIMEOUT):
                ms = int((time.time() - start) * 1000)
                return (True, ms)
        except ConnectionRefusedError:
            ms = int((time.time() - start) * 1000)
            return (True, ms)
        except OSError:
            continue
    return (False, -1)


def ssh_command(ip: str, command: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             ip, command],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 or result.returncode == 255:
            return (True, "")
        return (False, result.stderr.strip() or "SSH command failed")
    except subprocess.TimeoutExpired:
        return (True, "")
    except Exception as e:
        return (False, str(e))


# ── Start ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("🏝️  Archipelago is running!")
    print(f"   Open http://localhost:{PORT} in your browser")
    print(f"   Or on Tailscale: http://<this-machine-ip>:{PORT}")
    print()
    app.run(host="0.0.0.0", port=PORT, debug=False)
