import subprocess
import requests
import time
import hashlib
import json

# --- Config ---
ADB_DEVICE = "192.168.100.5:45131"
API_URL = "https://sms-gateway-hjno.onrender.com/webhook/sms"
POLL_INTERVAL = 10  # seconds between checks

# Track already sent messages to avoid duplicates
seen_ids = set()

def get_sms():
    """Pull SMS from phone via ADB."""
    result = subprocess.run(
        ["adb", "-s", ADB_DEVICE, "shell", "content", "query", "--uri", "content://sms/inbox"],
        capture_output=True,
        text=True
    )
    return result.stdout


def parse_sms(raw):
    """Parse ADB SMS output into a list of dicts."""
    messages = []
    for line in raw.strip().split("\n"):
        if not line.startswith("Row:"):
            continue
        msg = {}
        for part in line.split(", "):
            if "=" in part:
                key, _, value = part.partition("=")
                msg[key.strip().lstrip("Row: 0123456789")] = value.strip()
        if msg:
            messages.append(msg)
    return messages


def forward_sms(msg):
    """Post a single SMS to the API webhook."""
    payload = {
        "from": msg.get("address", "Unknown"),
        "message": msg.get("body", ""),
        "date": msg.get("date", "")
    }
    try:
        response = requests.post(API_URL, json=payload)
        print(f"[FORWARDED] From: {payload['from']} | Status: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to forward: {e}")


def make_id(msg):
    """Create a unique ID for each message to avoid duplicates."""
    unique = f"{msg.get('address')}{msg.get('date')}{msg.get('body')}"
    return hashlib.md5(unique.encode()).hexdigest()


def poll():
    print(f"[POLLING] Checking for new SMS every {POLL_INTERVAL} seconds...")
    print(f"[TARGET] {ADB_DEVICE} → {API_URL}\n")

    while True:
        try:
            raw = get_sms()
            messages = parse_sms(raw)

            new_count = 0
            for msg in messages:
                msg_id = make_id(msg)
                if msg_id not in seen_ids:
                    seen_ids.add(msg_id)
                    forward_sms(msg)
                    new_count += 1

            if new_count == 0:
                print(f"[OK] No new messages. Total tracked: {len(seen_ids)}")

        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    poll()