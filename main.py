from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uvicorn
import uuid

app = FastAPI(title="SMS Gateway API", description="Receives and serves forwarded SMS messages")

# --- Simple in-memory store (replace with a DB like SQLite/Postgres for production) ---
sms_store = []

# --- API Key Auth (set your own secret key here) ---
API_KEY = "your-secret-api-key-change-this"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return key


# --- Models ---
class SMSPayload(BaseModel):
    from_number: Optional[str] = None  # sender's number
    message: Optional[str] = None      # SMS body
    # Some forwarder apps use different field names — we handle both below
    from_: Optional[str] = None
    text: Optional[str] = None
    body: Optional[str] = None
    sender: Optional[str] = None


# --- Webhook: Phone app posts here when SMS arrives ---
@app.post("/webhook/sms")
async def receive_sms(request: Request):
    """
    The SMS forwarder app on your phone will POST to this endpoint.
    Supports multiple field name formats used by different apps.
    """
    try:
        data = await request.json()
    except Exception:
        # Some apps send form data instead of JSON
        form = await request.form()
        data = dict(form)

    # Normalize field names from different SMS forwarder apps
    sender = (
        data.get("from")
        or data.get("from_number")
        or data.get("sender")
        or data.get("phoneNumber")
        or "Unknown"
    )
    message = (
        data.get("message")
        or data.get("text")
        or data.get("body")
        or data.get("smsBody")
        or "No content"
    )

    sms_entry = {
        "id": str(uuid.uuid4()),
        "from": sender,
        "message": message,
        "received_at": datetime.utcnow().isoformat() + "Z",
        "raw": data  # store raw payload for debugging
    }

    sms_store.append(sms_entry)
    print(f"[SMS RECEIVED] From: {sender} | Message: {message}")

    return {"status": "received", "id": sms_entry["id"]}


# --- GET all messages (protected) ---
@app.get("/sms", dependencies=[Depends(verify_api_key)])
def get_all_sms(limit: int = 50, offset: int = 0):
    """
    Returns all received SMS messages, newest first.
    Protected by API key — pass header: X-API-Key: your-secret-api-key-change-this
    """
    sorted_sms = list(reversed(sms_store))
    return {
        "total": len(sms_store),
        "messages": sorted_sms[offset: offset + limit]
    }


# --- GET latest message (protected) ---
@app.get("/sms/latest", dependencies=[Depends(verify_api_key)])
def get_latest_sms():
    """Returns the most recently received SMS."""
    if not sms_store:
        return {"message": None}
    return {"message": sms_store[-1]}


# --- GET single message by ID (protected) ---
@app.get("/sms/{sms_id}", dependencies=[Depends(verify_api_key)])
def get_sms_by_id(sms_id: str):
    for sms in sms_store:
        if sms["id"] == sms_id:
            return sms
    raise HTTPException(status_code=404, detail="SMS not found")


# --- DELETE all messages (protected) ---
@app.delete("/sms", dependencies=[Depends(verify_api_key)])
def clear_sms():
    sms_store.clear()
    return {"status": "cleared"}


# --- Health check ---
@app.get("/health")
def health():
    return {"status": "ok", "total_sms": len(sms_store)}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)