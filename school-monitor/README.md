# School Device Monitor

A minimal prototype for monitoring school-owned Windows laptops for
policy-violating activity (social media, gaming) and alerting an admin
dashboard.

## Before you deploy this anywhere

1. **Disclose it.** Add a clause to the school's acceptable-use policy that
   students and parents/guardians sign, stating that school devices are
   monitored for app/website usage and explaining what is and isn't
   collected. This protects the school legally and is the right thing to do.
2. **Only install on school-owned devices**, not personal devices.
3. **Minimize data collected.** This prototype only logs window titles and
   process names — not keystrokes, screenshots, messages, or browsing
   history beyond the title bar. Keep it that way unless the school's policy
   and legal counsel say otherwise.
4. **Secure the dashboard** before going live: change `ADMIN_USERNAME`,
   `ADMIN_PASSWORD`, and `app.secret_key` in `dashboard/app.py`, and put the
   server behind HTTPS (e.g. with a reverse proxy like Caddy or nginx).

## How it works

- `agent/agent.py` runs on each laptop, checks the active window title and
  running processes every few seconds against `agent/policy.json`, and
  POSTs a violation report to the admin server when something matches.
- `dashboard/app.py` is a small Flask server that stores reports in SQLite
  and shows them in a web dashboard at `/admin`, filterable by student or
  category.

## Setup — Dashboard (run this on a server the laptops can reach)

```bash
cd dashboard
pip install -r requirements.txt
python app.py
```

Visit `http://<server-ip>:5000/admin` (default login `admin` / `changeme` —
change this first).

## Setup — Agent (run this on each Windows laptop)

```powershell
cd agent
pip install -r requirements.txt
# Edit policy.json: set server_url to http://<server-ip>:5000/api/alert
python agent.py
```

To run it permanently in the background as a Windows service (so it starts
at boot and isn't easily closed by a student):

1. Download [NSSM](https://nssm.cc/download).
2. `nssm install SchoolMonitor "C:\Path\to\python.exe" "C:\Path\to\agent.py"`
3. `nssm start SchoolMonitor`

Alternatively, use Windows Task Scheduler with a trigger "At log on" and
"Run with highest privileges", running as SYSTEM so a standard student
account can't stop it from Task Manager.

## Customizing the policy

Edit `agent/policy.json`. Each category has:
- `window_title_keywords`: case-insensitive substrings checked against the
  active window's title bar (catches "Instagram • Feed - Google Chrome").
- `process_names`: exact `.exe` names checked against all running
  processes (catches a game running even if its window isn't focused).

## Known limitations (read before relying on this)

- **Private/incognito browsing** and window titles that don't reveal the
  site (some sites blank the title) can't be detected by title matching
  alone. A more robust approach adds a **browser extension** that reports
  the actual URL — happy to build that next if useful.
- A technically savvy student could rename an executable or use a VPN/proxy
  to dodge keyword matching. No single-layer monitoring tool is bulletproof;
  pairing this with network-level filtering (e.g. DNS/content filtering on
  the school Wi-Fi) covers more ground.
- This prototype uses simple admin/password auth. For real deployment,
  integrate with the school's existing login system (e.g. Google Workspace
  SSO) rather than a hardcoded password.

## Next steps you might want

- A browser extension (Chrome/Edge) for accurate URL-level detection.
- Daily/weekly email digest to admins instead of only live alerts.
- Per-student history page instead of just the flat alert table.
- Packaging the agent as a signed `.exe` (via PyInstaller) for easier
  mass deployment.
