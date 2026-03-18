"""
Archipelago — backend
======================
Endpoints:
  GET  /api/machines  →  load saved machines list
  POST /api/machines  →  save machines list
  POST /api/wake      →  send WOL magic packet
  POST /api/ping      →  check if a machine is reachable
  POST /api/sleep     →  shut a machine down over SSH
  POST /api/reboot    →  reboot a machine over SSH

Requirements:
  pip install flask wakeonlan

Run directly:  python app.py
Run in Docker: docker compose up -d
"""

import json
import os
import socket
import subprocess
import time
from flask import Flask, request, jsonify, send_from_directory
from wakeonlan import send_magic_packet

app = Flask(__name__, static_folder="static")

# ── Config ────────────────────────────────────────────────────────

PORT = 5000

SSH_USER = "your_ssh_username"

PING_TIMEOUT = 2.0

CHECK_PORTS = [22, 80, 443]

# Machines are saved to this file — it lives in /data inside the
# container, which is mounted to a folder on the host so it persists.
MACHINES_FILE = "/data/machines.json"


# ── Frontend ──────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── Machines persistence ──────────────────────────────────────────

@app.route("/api/machines", methods=["GET"])
def get_machines():
    """Load machines list from disk."""
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
    """Save machines list to disk."""
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
    """Return whether a machine is reachable and its response time."""
    ip = request.get_json().get("ip", "").strip()
    if not ip:
        return jsonify({"error": "No IP provided"}), 400
    alive, ping_ms = check_host(ip)
    return jsonify({"alive": alive, "ping_ms": ping_ms})


@app.route("/api/wake", methods=["POST"])
def api_wake():
    """Send a WOL magic packet to the machine."""
    data = request.get_json()
    mac  = data.get("mac", "").strip()
    ip   = data.get("ip",  "").strip()
    if not mac:
        return jsonify({"ok": False, "error": "No MAC address provided"}), 400
    try:
        if ip:
            send_magic_packet(mac, ip_address=ip, port=9)
        else:
            send_magic_packet(mac)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sleep", methods=["POST"])
def api_sleep():
    """Shut a machine down via SSH."""
    ip = request.get_json().get("ip", "").strip()
    if not ip:
        return jsonify({"ok": False, "error": "No IP provided"}), 400
    ok, err = ssh_command(ip, "sudo shutdown -h now")
    return jsonify({"ok": ok, "error": err})


@app.route("/api/reboot", methods=["POST"])
def api_reboot():
    """Reboot a machine via SSH."""
    ip = request.get_json().get("ip", "").strip()
    if not ip:
        return jsonify({"ok": False, "error": "No IP provided"}), 400
    ok, err = ssh_command(ip, "sudo shutdown -r now")
    return jsonify({"ok": ok, "error": err})


# ── Helpers ───────────────────────────────────────────────────────

def check_host(ip: str) -> tuple[bool, int]:
    """Check if a host is reachable via TCP on common ports."""
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
    """Run a command on a remote machine via SSH."""
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=5",
                "-o", "BatchMode=yes",
                ip,
                command,
            ],
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
