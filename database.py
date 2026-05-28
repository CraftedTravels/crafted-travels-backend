"""
Database layer — works with SQLite locally and PostgreSQL in production (Railway).
The DATABASE_URL environment variable switches between them automatically.
"""
import os
from sqlalchemy import (
    Column, Integer, String, Text, create_engine, text
)
from sqlalchemy.orm import DeclarativeBase, Session

# ── Connection setup ──────────────────────────────────────────────────────────
_raw_url = os.getenv("DATABASE_URL", "")

if _raw_url.startswith("postgres://"):
    # Railway (and Heroku) use postgres://, but SQLAlchemy needs postgresql://
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = _raw_url or f"sqlite:///{os.path.join(os.path.dirname(__file__), 'inquiries.db')}"

engine = create_engine(
    DATABASE_URL,
    # SQLite needs this flag for multi-threaded use; harmless on Postgres
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


# ── ORM model ─────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


class Inquiry(Base):
    __tablename__ = "inquiries"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    platform    = Column(String(20),  nullable=False)   # 'instagram' | 'whatsapp'
    sender_id   = Column(String(100), nullable=False)
    sender_name = Column(String(200))
    message     = Column(Text,        nullable=False)
    raw_payload = Column(Text)
    status      = Column(String(20),  nullable=False, default="new")
    received_at = Column(String(30),  nullable=False,
                         server_default=text("(datetime('now'))") if DATABASE_URL.startswith("sqlite")
                                       else text("to_char(now() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')"))


def init_db():
    Base.metadata.create_all(engine)


# ── Write helpers ─────────────────────────────────────────────────────────────
def insert_inquiry(platform, sender_id, sender_name, message, raw_payload):
    with Session(engine) as session:
        row = Inquiry(
            platform=platform,
            sender_id=sender_id,
            sender_name=sender_name,
            message=message,
            raw_payload=raw_payload,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def update_status(inquiry_id, status):
    with Session(engine) as session:
        row = session.get(Inquiry, inquiry_id)
        if row:
            row.status = status
            session.commit()


# ── Read helpers ──────────────────────────────────────────────────────────────
def _row_to_dict(row: Inquiry) -> dict:
    return {
        "id":          row.id,
        "platform":    row.platform,
        "sender_id":   row.sender_id,
        "sender_name": row.sender_name,
        "message":     row.message,
        "raw_payload": row.raw_payload,
        "status":      row.status,
        "received_at": row.received_at,
    }


def list_inquiries(platform=None, status=None, limit=100, offset=0):
    with Session(engine) as session:
        q = session.query(Inquiry)
        if platform:
            q = q.filter(Inquiry.platform == platform)
        if status:
            q = q.filter(Inquiry.status == status)
        rows = q.order_by(Inquiry.id.desc()).limit(limit).offset(offset).all()
        return [_row_to_dict(r) for r in rows]


def get_inquiry(inquiry_id):
    with Session(engine) as session:
        row = session.get(Inquiry, inquiry_id)
        return _row_to_dict(row) if row else None


def count_inquiries(platform=None, status=None):
    with Session(engine) as session:
        q = session.query(Inquiry)
        if platform:
            q = q.filter(Inquiry.platform == platform)
        if status:
            q = q.filter(Inquiry.status == status)
        return q.count()
