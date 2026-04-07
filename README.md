# 🏝️ Archipelago

homelab control panel.
Wake, sleep, reboot, and ping machines on your Tailscale network.

## Folder structure

```
archipelago/
├── app.py              ← Python/Flask backend
├── Dockerfile
├── docker-compose.yml
├── README.md
└── static/
    └── index.html      ← The UI
```

## Quick start

```bash
docker compose up -d
```

Then open **http://localhost:5000** (or your Tailscale IP on port 5000).

---

## One-time setup

### 1. Set your SSH username

Edit `app.py` and change this line near the top:

```python
SSH_USER = "your_ssh_username"
```

### 2. Set up SSH keys

Archipelago SSHes into your machines to run shutdown/reboot.
Run these commands **on the machine that will run Archipelago**:

```bash
# Generate a key if you don't have one yet
ssh-keygen -t ed25519

# Copy your key to each machine you want to control
ssh-copy-id your_user@100.x.x.x
```

### 3. Allow passwordless shutdown on each target machine

On each machine you want to sleep/reboot, run `sudo visudo` and add:

```
your_user ALL=(ALL) NOPASSWD: /sbin/shutdown
```

### 4. WOL — make sure it's enabled in BIOS

In your machine's BIOS/UEFI settings, look for:
- "Wake on LAN" → Enabled
- "ERP" or "ErP Ready" → Disabled (this disables WOL if enabled)

---

## How the buttons work

| Button | What happens |
|--------|-------------|
| ☀️ Wake | Sends a WOL magic packet to the machine's Tailscale IP |
| 🌙 Sleep | SSHes in and runs `sudo shutdown -h now` |
| 🔄 Reboot | SSHes in and runs `sudo shutdown -r now` |
| 🏓 Ping | Runs automatically every 15 seconds |

## Notes on Tailscale + WOL

WOL magic packets are sent **directly to the Tailscale IP** rather than
a broadcast address. This is more reliable and avoids subnet/router issues.

The machine still needs to support WOL at the hardware level. The Tailscale
connection is only used for the management side (ping, sleep, reboot).

## TODO

-⬜ Network scan / device discovery
-⬜ Per-user permissions
