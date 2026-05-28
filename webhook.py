"""
Parses raw Meta webhook payloads for both Instagram and WhatsApp.
Returns a list of normalised inquiry dicts or an empty list if nothing actionable.
"""
import json


def parse_payload(body: dict) -> list[dict]:
    object_type = body.get("object", "")

    if object_type == "instagram":
        return _parse_instagram(body)
    elif object_type == "whatsapp_business_account":
        return _parse_whatsapp(body)
    return []


def _parse_instagram(body: dict) -> list[dict]:
    results = []
    for entry in body.get("entry", []):
        for msg_event in entry.get("messaging", []):
            sender_id = msg_event.get("sender", {}).get("id")
            message_obj = msg_event.get("message", {})
            text = message_obj.get("text")
            if not sender_id or not text:
                continue
            results.append({
                "platform": "instagram",
                "sender_id": sender_id,
                "sender_name": None,
                "message": text,
            })
    return results


def _parse_whatsapp(body: dict) -> list[dict]:
    results = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {c["wa_id"]: c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                msg_type = msg.get("type")
                sender_id = msg.get("from")
                if msg_type == "text":
                    text = msg.get("text", {}).get("body", "")
                elif msg_type == "image":
                    text = "[Image]"
                elif msg_type == "audio":
                    text = "[Audio message]"
                elif msg_type == "document":
                    text = "[Document]"
                else:
                    text = f"[{msg_type}]"
                if not sender_id or not text:
                    continue
                results.append({
                    "platform": "whatsapp",
                    "sender_id": sender_id,
                    "sender_name": contacts.get(sender_id),
                    "message": text,
                })
    return results
