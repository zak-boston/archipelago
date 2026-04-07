# 🏝️ Archipelago
 
A homelab control panel for your network.
Wake, sleep, reboot, ping, and schedule machines.
 
## Folder structure
 
```
archipelago/
├── app.py
├── Dockerfile
├── docker-compose.yml
├── README.md
└── static/
    └── index.html
```
 
## Quick start
 
```
docker compose up -d
```
 
Then open **http://localhost:5000** (or your Tailscale IP on port 5000).
 
---
 
## One-time setup
 
### 1. Set environment variables
 
Edit `docker-compose.yml` and set these under `environment`:
 
```yaml
environment:
  - ARCHIPELAGO_PASSWORD=your_password_here
  - ARCHIPELAGO_SSH_USER=your_ssh_username
```
 
`ARCHIPELAGO_PASSWORD` is required to log in to the UI.
`ARCHIPELAGO_SSH_USER` is the username used for SSH sleep/reboot commands.
The app will refuse to start if either is missing.
 
### 2. Set up SSH keys
 
Archipelago SSHes into your machines to run shutdown/reboot.
Run these commands **on the machine that will run Archipelago**:
 
```
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
 
* "Wake on LAN" → Enabled
* "After Power Loss" → "Power On"
* "ERP" or "ErP Ready" → Disabled (this disables WOL if enabled)
 
---
 
## Features
 
| Feature | Details |
| --- | --- |
| ☀️ Wake | Sends a WOL magic packet to the machine's IP |
| 🌙 Sleep | SSHes in and runs `sudo shutdown -h now` |
| 🔄 Reboot | SSHes in and runs `sudo shutdown -r now` |
| 🏓 Ping | Automatic status check every 15 seconds |
| 🔌 Per-port monitoring | Configure which ports to check per machine |
| ⏰ Schedules | Wake or sleep machines automatically on a time + day schedule |
| 💾 Backup | One-click JSON download of all your machines |
| 📂 Restore | Restore machines from a backup file via the UI |
| 🔍 Search | Filter machines by name or role |
| ↔️ Drag to reorder | Drag machine cards to rearrange them |
| 🔒 Password auth | Login page protects all actions |
 
---
 
## Schedules
 
The schedules section lets you automatically wake or sleep machines at set times on chosen days. Schedules survive container restarts and are stored in `data/schedules.json`.
 
---
 
## Backup and restore
 
Click **💾 Backup** in the top bar to download `archipelago-backup-YYYY-MM-DD.json`. To restore, click **📂 Restore** and pick the file — this replaces all current machines in the UI and saves immediately.
 
---
 
## Data storage
 
Machine and schedule data is saved to `./data/` on the host via the Docker volume mount:
 
```yaml
volumes:
  - ./data:/data
```
 
This means your data survives container rebuilds and restarts.
 
---
 
## Updating
 
```
docker compose down
docker compose up -d --build
```
 
Your data in `./data/` is untouched by rebuilds.
 
---
 
## Tech stack
 
| Layer | What |
| --- | --- |
| Backend | Python 3.12, Flask, APScheduler, wakeonlan |
| Frontend | Vanilla HTML/CSS/JS — no framework, no build step |
| Storage | JSON files on disk |
| Container | Docker + Compose |
 
---
 
## TODO
 
- ⬜ Network scan / device discovery (requires nmap)
- ⬜ Per-user per-device permissions
- ⬜ Themes
