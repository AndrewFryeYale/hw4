"""Campus Customs API: product catalogue, product images, auth, and the chatbot.

Run from the hw4/backend folder:
    ../venv/bin/uvicorn main:app --reload --port 8000
"""

import logging
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

import agent
from auth import (SESSION_COOKIE, SESSION_DAYS, create_session, delete_session, ensure_sessions_table,
                  hash_password, user_for_session, verify_password)
from models import AuditEntry, CatalogueProduct, ChatReply, ChatRequest, HistoryMessage
from tools import append_audit_entry, redact, load_catalogue_products, load_chat_history, load_customer_memory, save_chat_exchange

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"

app = FastAPI(title="Campus Customs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,  # session cookie (the Vite proxy makes calls same-origin anyway)
)

# image_file_path in the DB is relative to data/ (e.g. "products/x.jpg"),
# so it is served at /media/products/x.jpg — the same image_url shape
# already stored in chat_messages.products_json. Only the products folder is
# mounted so the database file itself is never reachable over HTTP.
app.mount(
    "/media/products", StaticFiles(directory=DATA_DIR / "products"), name="products"
)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_writable_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


with get_writable_db() as _conn:
    ensure_sessions_table(_conn)  # creates `sessions` on first run, prunes expired rows


def _start_session(response: Response, user_id: int) -> None:
    with get_writable_db() as conn:
        token = create_session(conn, user_id)
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", path="/",
        # secure=True once the site is served over HTTPS
    )


def session_user(token: str | None) -> sqlite3.Row | None:
    with get_db() as conn:
        return user_for_session(conn, token)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Product records are built by tools.load_catalogue_products, the same function that fills chat
# page updates, so the Products page renders catalogue and chat results identically.
@app.get("/api/products", response_model=list[CatalogueProduct])
def list_products() -> list[CatalogueProduct]:
    return load_catalogue_products()


@app.get("/api/products/{product_id}", response_model=CatalogueProduct)
def get_product(product_id: str) -> CatalogueProduct:
    found = load_catalogue_products([product_id])
    if not found:
        raise HTTPException(status_code=404, detail="Product not found")
    return found[0]


# ---------------------------------------------------------------------------
# Auth: create account / log in. Passwords are hashed via backend.auth and the
# raw password or stored hash is never returned to the client.
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PublicUser(BaseModel):
    id: int
    first_name: str | None
    last_name: str | None
    name: str
    email: str


def _public_user(row: sqlite3.Row) -> PublicUser:
    return PublicUser(
        id=row["id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        name=row["name"],
        email=row["email"],
    )


@app.post("/api/auth/register", response_model=PublicUser, status_code=201)
def register(body: RegisterRequest, response: Response) -> PublicUser:
    email = body.email.lower().strip()
    full_name = f"{body.first_name.strip()} {body.last_name.strip()}"
    password_hash = hash_password(body.password)
    with get_writable_db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="An account with that email already exists.")
        cur = conn.execute(
            """INSERT INTO users (name, email, password_hash, first_name, last_name)
               VALUES (?, ?, ?, ?, ?)""",
            (full_name, email, password_hash, body.first_name.strip(), body.last_name.strip()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    _start_session(response, row["id"])
    return _public_user(row)


@app.post("/api/auth/login", response_model=PublicUser)
def login(body: LoginRequest, response: Response) -> PublicUser:
    email = body.email.lower().strip()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    # Verify even when the user is missing (dummy hash) to avoid leaking which
    # emails exist via response timing.
    stored = row["password_hash"] if row else "pbkdf2_sha256$0$deadbeef$deadbeef"
    if not verify_password(body.password, stored) or row is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    _start_session(response, row["id"])
    return _public_user(row)


@app.get("/api/auth/me", response_model=PublicUser | None)
def me(cc_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> PublicUser | None:
    """Who the session cookie belongs to, or null for a guest (200 either way, so guests don't log errors).
    The front end calls this on load to confirm a saved login."""
    row = session_user(cc_session)
    return _public_user(row) if row else None


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response, cc_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> None:
    with get_writable_db() as conn:
        delete_session(conn, cc_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


# ---------------------------------------------------------------------------
# Chatbot: the widget POSTs the new message plus earlier turns; the Pydantic AI
# agent (agent.py) answers with reply text and product cards.
# ---------------------------------------------------------------------------

logger = logging.getLogger("campus_customs.chat")

# Guardrail: per-customer rate limit on the (paid) chat endpoint. Keyed by user id when logged in, else by
# client IP. In-memory sliding window, so it resets on server restart, which is fine for one process.
CHAT_RATE_LIMIT = 20  # messages
CHAT_RATE_WINDOW_S = 10 * 60  # per 10 minutes
_chat_hits: dict[str, deque[float]] = defaultdict(deque)
_chat_hits_lock = threading.Lock()


def _allow_chat(key: str) -> bool:
    now = time.monotonic()
    with _chat_hits_lock:
        hits = _chat_hits[key]
        while hits and now - hits[0] > CHAT_RATE_WINDOW_S:
            hits.popleft()
        if len(hits) >= CHAT_RATE_LIMIT:
            return False
        hits.append(now)
        return True


@app.post("/api/chat", response_model=ChatReply)
async def chat(request: Request, body: ChatRequest, cc_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> ChatReply:
    # Identity comes only from the session cookie, never from the request body.
    user = session_user(cc_session)
    key = f"user:{user['id']}" if user else f"ip:{request.client.host if request.client else 'unknown'}"
    if not _allow_chat(key):
        append_audit_entry(AuditEntry(
            run_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc).isoformat(),
            customer="logged_in" if user else "guest", user_id=user["id"] if user else None,
            page_path=body.page.path if body.page else None, page_product_id=body.page.product_id if body.page else None,
            message=redact(body.message), history_turns=0, model=agent.MODEL_NAME, prompt_sections=[],
            limits={"chat_rate_limit": CHAT_RATE_LIMIT, "chat_rate_window_s": CHAT_RATE_WINDOW_S},
            outcome="rate_limited", error="rate limit exceeded; agent not called", latency_ms=0,
        ))
        raise HTTPException(
            status_code=429,
            detail="You're sending messages faster than I can keep up. Please wait a few minutes and try again.",
        )
    customer = load_customer_memory(user) if user else None
    try:
        reply = await agent.chat(body, customer)
    except Exception:
        logger.exception("chat agent failed")
        raise HTTPException(
            status_code=502,
            detail="The assistant is having trouble right now. Please try again in a moment.",
        )
    if user:  # guests can chat, but only logged-in customers' conversations are saved
        save_chat_exchange(user["id"], body.message, reply)
    return reply


@app.get("/api/chat/history", response_model=list[HistoryMessage])
def chat_history(cc_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> list[HistoryMessage]:
    """The logged-in customer's saved chat, so the widget can redraw it when they return."""
    user = session_user(cc_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Log in to see your chat history.")
    return load_chat_history(user["id"])
