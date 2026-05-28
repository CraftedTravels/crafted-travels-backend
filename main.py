import json
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
import webhook as wh

load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")

app = FastAPI(title="Crafted Travels — Inquiry Logger")

# ── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    db.init_db()


# ── Meta webhook ─────────────────────────────────────────────────────────────

@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta calls this GET to verify ownership of the webhook URL."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Meta sends all Instagram DMs and WhatsApp messages here."""
    body = await request.json()
    raw = json.dumps(body)
    inquiries = wh.parse_payload(body)
    for inq in inquiries:
        db.insert_inquiry(
            platform=inq["platform"],
            sender_id=inq["sender_id"],
            sender_name=inq["sender_name"],
            message=inq["message"],
            raw_payload=raw,
        )
    return {"status": "ok", "logged": len(inquiries)}


# ── REST API ──────────────────────────────────────────────────────────────────

@app.get("/api/inquiries")
def get_inquiries(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    rows = db.list_inquiries(platform=platform, status=status, limit=limit, offset=offset)
    total = db.count_inquiries(platform=platform, status=status)
    return {"total": total, "items": rows}


@app.get("/api/inquiries/{inquiry_id}")
def get_inquiry(inquiry_id: int):
    row = db.get_inquiry(inquiry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


class StatusUpdate(BaseModel):
    status: str


@app.patch("/api/inquiries/{inquiry_id}")
def patch_inquiry(inquiry_id: int, body: StatusUpdate):
    if body.status not in ("new", "read", "responded"):
        raise HTTPException(status_code=400, detail="status must be new | read | responded")
    if not db.get_inquiry(inquiry_id):
        raise HTTPException(status_code=404, detail="Not found")
    db.update_status(inquiry_id, body.status)
    return db.get_inquiry(inquiry_id)


@app.get("/api/stats")
def get_stats():
    return {
        "total": db.count_inquiries(),
        "instagram": db.count_inquiries(platform="instagram"),
        "whatsapp": db.count_inquiries(platform="whatsapp"),
        "new": db.count_inquiries(status="new"),
        "read": db.count_inquiries(status="read"),
        "responded": db.count_inquiries(status="responded"),
    }


# ── Admin dashboard (served at /) ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html")) as f:
        return f.read()


app.mount("/static", StaticFiles(directory="static"), name="static")
