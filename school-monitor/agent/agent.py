"""
School Device Monitor - Client Agent (Windows)
------------------------------------------------
Runs in the background on a school-owned Windows laptop. Periodically checks
the active window title and running processes against a policy file. When a
match is found, it reports the violation to the admin server.

IMPORTANT (read before deploying):
- Only install this on devices the school owns and that are covered by a
  signed acceptable-use / monitoring-disclosure policy. Students and
  parents/guardians should know this software is present and what it does.
- This agent intentionally does NOT hide itself, read private messages,
  capture keystrokes, or inspect encrypted traffic. It only looks at window
  titles and process names, which is enough to catch "going on Instagram" or
  "playing Roblox" without being invasive.

Dependencies:
    pip install psutil pywin32 requests

Run manually for testing:
    python agent.py

For production, wrap this with NSSM (https://nssm.cc/) or Task Scheduler
to run it as a Windows service / at-logon task running as SYSTEM.
"""

import json
import time
import socket
import getpass
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

import psutil
import requests

try:
    import win32gui
    import win32process
except ImportError:
    raise SystemExit(
        "pywin32 is required. Install with: pip install pywin32"
    )

CONFIG_PATH = Path(__file__).parent / "policy.json"
LOG_PATH = Path(__file__).parent / "agent.log"

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def load_policy():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_device_id():
    """Stable-ish device identifier based on MAC address."""
    return f"{socket.gethostname()}-{uuid.getnode():x}"


def get_active_window_info():
    """Return (window_title, process_name) for the currently focused window."""
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return "", ""
    title = win32gui.GetWindowText(hwnd)
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        proc_name = proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        proc_name = ""
    return title, proc_name


def get_running_process_names():
    names = set()
    for p in psutil.process_iter(["name"]):
        try:
            n = p.info["name"]
            if n:
                names.add(n.lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return names


def check_violations(policy, window_title, active_process, running_processes):
    """Return a list of (category, matched_on, matched_value) tuples."""
    violations = []
    title_lower = window_title.lower()

    for category, rules in policy["categories"].items():
        for kw in rules.get("window_title_keywords", []):
            if kw.lower() in title_lower:
                violations.append((category, "window_title", window_title))
                break

        for proc_name in rules.get("process_names", []):
            if proc_name.lower() in running_processes:
                violations.append((category, "process", proc_name))

    return violations


def send_alert(policy, device_id, username, category, matched_on, matched_value, window_title):
    payload = {
        "device_id": device_id,
        "username": username,
        "category": category,
        "matched_on": matched_on,
        "matched_value": matched_value,
        "window_title": window_title,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = requests.post(policy["server_url"], json=payload, timeout=5)
        resp.raise_for_status()
        logging.info("Reported violation: %s", payload)
    except requests.RequestException as e:
        logging.warning("Failed to send alert (will retry next poll): %s", e)


def main():
    policy = load_policy()
    device_id = get_device_id()
    username = getpass.getuser()

    # Avoid spamming repeat alerts for the same ongoing activity
    last_reported = set()

    logging.info("Agent started on device %s as user %s", device_id, username)

    while True:
        try:
            window_title, active_process = get_active_window_info()
            running_processes = get_running_process_names()

            violations = check_violations(
                policy, window_title, active_process, running_processes
            )

            current_keys = set()
            for category, matched_on, matched_value in violations:
                key = (category, matched_on, matched_value)
                current_keys.add(key)
                if key not in last_reported:
                    send_alert(
                        policy, device_id, username,
                        category, matched_on, matched_value, window_title,
                    )

            last_reported = current_keys

        except Exception as e:
            logging.exception("Unexpected error in monitor loop: %s", e)

        time.sleep(policy.get("poll_interval_seconds", 5))


if __name__ == "__main__":
    main()
