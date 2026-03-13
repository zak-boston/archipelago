"""
Archipelago — backend
======================
Endpoints:
  POST /api/wake    →  send WOL magic packet
  POST /api/ping    →  check if a machine is reachable
  POST /api/sleep   →  shut a machine down over SSH
  POST /api/reboot  →  reboot a machine over SSH

Requirements:
  pip install flask wakeonlan

Run directly:  python app.py
Run in Docker: docker compose up -d
"""

import subprocess
import time
from flask import Flask, request, jsonify, send_from_directory
from wakeonlan import send_magic_packet

app = Flask(__name__, static_folder="static")

# ── Config ────────────────────────────────────────────────────────

PORT = 5000

# SSH username used to reach target machines for sleep/reboot.
# This user needs passwordless SSH key access from the server running
# Archipelago. See README for setup instructions.
SSH_USER = "your_ssh_username"

# Seconds to wait for a ping reply before declaring offline.
PING_TIMEOUT = 1.5


# ── Frontend ──────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ── API ───────────────────────────────────────────────────────────

@app.route("/api/ping", methods=["POST"])
def api_ping():
    """Return whether a machine is reachable and its response time."""
    ip = request.get_json().get("ip", "").strip()
    if not ip:
        return jsonify({"error": "No IP provided"}), 400
    alive, ping_ms = ping_host(ip)
    return jsonify({"alive": alive, "ping_ms": ping_ms})


@app.route("/api/wake", methods=["POST"])
def api_wake():
    """Send a WOL magic packet directly to the machine's Tailscale IP."""
    data = request.get_json()
    mac  = data.get("mac", "").strip()
    ip   = data.get("ip",  "").strip()
    if not mac:
        return jsonify({"ok": False, "error": "No MAC address provided"}), 400
    try:
        if ip:
            # Tailscale IP: send directly — no broadcast needed
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

def ping_host(ip: str) -> tuple[bool, int]:
    """Ping once; return (alive, ms). ms is -1 if no response."""
    try:
        start = time.time()
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(PING_TIMEOUT * 1000)), ip],
            capture_output=True, text=True,
            timeout=PING_TIMEOUT + 1,
        )
        ms = int((time.time() - start) * 1000)
        return (result.returncode == 0, ms if result.returncode == 0 else -1)
    except Exception:
        return (False, -1)


def ssh_command(ip: str, command: str) -> tuple[bool, str]:
    """
    Run a command on a remote machine via SSH.

    Requirements on the target machine:
      - SSH enabled
      - SSH key from this server copied over (ssh-copy-id)
      - Passwordless sudo for shutdown:
          Add to /etc/sudoers via `sudo visudo`:
          your_user ALL=(ALL) NOPASSWD: /sbin/shutdown
    """
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=5",
                "-o", "BatchMode=yes",
                f"{SSH_USER}@{ip}",
                command,
            ],
            capture_output=True, text=True, timeout=10,
        )
        # A machine that shuts down mid-SSH may return non-zero — that's fine
        if result.returncode == 0 or result.returncode == 255:
            return (True, "")
        return (False, result.stderr.strip() or "SSH command failed")
    except subprocess.TimeoutExpired:
        # Machine powered off while we were connected — success
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
