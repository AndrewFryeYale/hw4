"""Tools the Campus Customs chatbot can call, plus the helpers agent.py uses around them.

Agent tools (registered in agent.py). Each reads campus_customs.db (read-only) and returns a typed model
from models.py, so the agent only ever sees real database values:
    search_products      -> SearchResults   keyword / color / price / size search over the catalogue
    get_product_details  -> ProductDetails  description, colors, tags, price and stock per size for one product
    get_prices           -> list[PriceQuote] exact prices for one or more products
    check_stock          -> StockReport     units in stock for one product, one size or all sizes

Helpers:
    load_prompt         - read a `## <name>` section of prompts/prompt.md
    validate_reply      - output validator: ids, $ prices and stock counts in a reply must come from a tool
    load_product_cards  - build models.ProductCard objects from the DB for the ids the agent picked
    load_catalogue_products - full product records (GET /api/products shape) for /api/products and page updates

Customer memory (logged-in customers; chat_messages table):
    render_page_context      - which page / product the customer is looking at, for the agent's instructions
    load_customer_memory     - profile + recent turns + older highlights for the agent's context
    render_customer_context  - CustomerMemory -> the text block added to the agent's instructions
    save_chat_exchange       - write the customer's message and the assistant's reply to chat_messages
    load_chat_history        - saved messages for the chat widget to redraw when the customer returns

Audit trail (output/audit_trail.json):
    audit_steps         - the agent loop's messages -> ordered AuditSteps (model replies, tool calls/results, retries)
    append_audit_entry  - append one AuditEntry; earlier entries are never rewritten or wiped
"""

from __future__ import annotations

import fcntl
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

from pydantic_ai import ModelRetry, RunContext

from models import (MAX_PAGE_RESULTS, AgentReply, AuditEntry, AuditStep, AuditUsage, CatalogueProduct, ChatReply, CustomerMemory, CustomerProfile,
                    HistoryMessage, InventoryItem, PageContext, PriceQuote, ProductCard, ProductDetails, ProductMention,
                    ProductSummary, SearchResults, SizeStock, StockReport, StoredMessage)

BACKEND_DIR = Path(__file__).resolve().parent
PROMPTS_PATH = BACKEND_DIR / "prompts" / "prompt.md"
AUDIT_PATH = BACKEND_DIR.parent / "output" / "audit_trail.json"
DB_PATH = BACKEND_DIR.parent / "data" / "campus_customs.db"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
MAX_RESULTS = 8
MAX_SEARCH_LIMIT = MAX_PAGE_RESULTS

# Shopper word -> any of these catalogue spellings counts as a match.
SYNONYMS = {
    "tee": ("t-shirt", "tee"), "tees": ("t-shirt", "tee"), "tshirt": ("t-shirt",), "t-shirts": ("t-shirt",),
    "hoodie": ("hood",), "hoodies": ("hood",), "hooded": ("hood",),
    "sweatshirts": ("sweatshirt",), "sweater": ("sweater", "sweatshirt", "crewneck", "fleece"),
    "crew": ("crew",), "crewnecks": ("crewneck",),
    "quarterzip": ("quarter-zip", "1/4 zip"), "1/4": ("quarter-zip", "1/4"),
    "jackets": ("jacket",), "grey": ("gray",), "gray": ("gray",),
}
STOPWORDS = {"a", "an", "the", "and", "or", "for", "with", "in", "of", "to", "me", "my", "any", "do",
             "you", "have", "show", "some", "something", "i", "want", "need", "looking", "yale"}


@dataclass
class ChatDeps:
    """Per-request state. The seen_* sets record what the database actually told the agent this run;
    validate_reply only lets ids, prices and stock counts from these sets into the reply."""

    db_path: Path = DB_PATH
    customer: CustomerMemory | None = None  # None = guest
    page: PageContext | None = None  # where the customer is on the site
    customer_text: str = ""  # everything the customer typed (their own numbers, e.g. a budget, are fine to echo)
    seen_ids: set[str] = field(default_factory=set)
    seen_prices: set[float] = field(default_factory=set)
    seen_quantities: set[int] = field(default_factory=set)

    def remember(self, product_id: str, prices: list[float] = (), quantities: list[int] = ()) -> None:
        self.seen_ids.add(product_id)
        self.seen_prices.update(round(p, 2) for p in prices)
        self.seen_quantities.update(quantities)


def load_prompt(name: str) -> str:
    """Return the text under `## <name>` in prompts/prompt.md."""
    text = PROMPTS_PATH.read_text()
    match = re.search(rf"^## {re.escape(name)}\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)
    if not match:
        raise KeyError(f"no '## {name}' section in {PROMPTS_PATH}")
    return match.group(1).strip()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _stock(conn: sqlite3.Connection, product_ids: list[str]) -> dict[str, dict[str, int]]:
    if not product_ids:
        return {}
    marks = ",".join("?" * len(product_ids))
    out: dict[str, dict[str, int]] = {}
    for r in conn.execute(f"SELECT product_id, size, quantity FROM inventory WHERE product_id IN ({marks})", product_ids):
        out.setdefault(r["product_id"], {})[r["size"]] = r["quantity"]
    return {pid: dict(sorted(s.items(), key=lambda kv: SIZE_ORDER.index(kv[0]) if kv[0] in SIZE_ORDER else 99))
            for pid, s in out.items()}


def _catalogue_row(conn: sqlite3.Connection, product_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    if row is None:
        raise ModelRetry(f"No product with id {product_id!r}. Use search_products to find the right id.")
    return row


def _size(size: str) -> str:
    s = size.upper().strip()
    s = {"SMALL": "S", "MEDIUM": "M", "LARGE": "L", "EXTRA SMALL": "XS", "EXTRA LARGE": "XL", "2XL": "XXL"}.get(s, s)
    if s not in SIZE_ORDER:
        raise ModelRetry(f"Unknown size {size!r}. Sizes are {', '.join(SIZE_ORDER)}.")
    return s


def _terms(query: str) -> list[tuple[str, ...]]:
    """Each query word becomes a tuple of spellings; the word matches if any spelling appears."""
    words = re.findall(r"[a-z0-9/'-]+", query.lower())
    return [SYNONYMS.get(w, (w,)) for w in words if w not in STOPWORDS and not w.startswith("$")]


def _hit(alts: tuple[str, ...], text: str) -> bool:
    return any(a in text for a in alts)


NAME_BOOST = 1.5  # a query word in the product name counts more than one in the description/tags
RELEVANCE_FLOOR = 0.5  # keep matches scoring >= this fraction of the best match


def _idf(doc_freq: int, total: int) -> float:
    """Inverse document frequency: how distinctive a query word is across the catalogue."""
    return math.log((total + 1) / (doc_freq + 1)) + 0.1


@lru_cache(maxsize=4)
def _vocabulary(db_path: Path) -> tuple[str, ...]:
    """Every word the catalogue uses (names, types, colors, tags, descriptions), for typo correction."""
    with _connect(db_path) as conn:
        text = " ".join(_haystack(r) for r in conn.execute("SELECT * FROM catalogue"))
    return tuple(sorted(set(re.findall(r"[a-z][a-z'-]{2,}", text))))


def _correct_typos(terms: list[tuple[str, ...]], db_path: Path) -> tuple[list[tuple[str, ...]], dict[str, str]]:
    """Swap misspelled query words for the closest catalogue word ("crewnek" -> "crewneck").

    A word is left alone if it already appears inside some catalogue word (so "zip" or "hood" still
    match as substrings), if it's short, or if nothing is close enough (cutoff 0.8)."""
    vocab = _vocabulary(db_path)
    fixed, corrections = [], {}
    for alts in terms:
        word = alts[0]
        if len(alts) > 1 or len(word) < 4 or not word.isalpha() or any(word in v for v in vocab):
            fixed.append(alts)
            continue
        close = get_close_matches(word, vocab, n=1, cutoff=0.8)
        if close:
            corrections[word] = close[0]
            fixed.append(SYNONYMS.get(close[0], (close[0],)))
        else:
            fixed.append(alts)
    return fixed, corrections


def _haystack(row: sqlite3.Row) -> str:
    parts = [row["name"], row["garment_type"], row["description"],
             " ".join(json.loads(row["colors"])), " ".join(json.loads(row["search_tags"]))]
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------


def search_products(
    ctx: RunContext[ChatDeps],
    query: str = "",
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    limit: int = MAX_RESULTS,
) -> SearchResults:
    """Search the Campus Customs catalogue. Returns up to `limit` matches, best first.

    Use this to find products. For exact stock counts use check_stock; for full descriptions use
    get_product_details. Put price, color and size limits in the filter arguments, not in the query.

    Args:
        query: What the customer wants in a few words, e.g. "grey hoodie", "residential college crewneck",
            "hockey t-shirt", "gift for dad". Leave empty to browse with only the filters.
        color: Only products offered in this color, e.g. "pink".
        max_price: Only products at or under this price in USD.
        size: Only products with this size in stock (XS, S, M, L, XL, XXL).
        limit: Max matches (1-30). Use 8 to pick a few recommendations; use 30 when the customer is
            browsing ("what hoodies do you have?") so the Products page can show every match.
    """
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    terms, corrections = _correct_typos(_terms(query), ctx.deps.db_path)
    color_alts = SYNONYMS.get(color.lower().strip(), (color.lower().strip(),)) if color else None
    size_u = _size(size) if size else None

    with _connect(ctx.deps.db_path) as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()
        texts = {r["product_id"]: _haystack(r) for r in rows}
        # Rare words say more than common ones: "saybrook" (4 products) outweighs "college" (30).
        weights = [_idf(sum(_hit(t, x) for x in texts.values()), len(rows)) for t in terms]
        scored = []
        for row in rows:
            if max_price is not None and row["price"] > max_price:
                continue
            if color_alts and not _hit(color_alts, " ".join(json.loads(row["colors"])).lower()):
                continue
            name = row["name"].lower()
            score = sum(w * (NAME_BOOST if _hit(t, name) else 1)
                        for t, w in zip(terms, weights) if _hit(t, texts[row["product_id"]]))
            if terms and score == 0:
                continue
            scored.append((score, row))
        scored.sort(key=lambda sr: (-sr[0], sr[1]["name"]))
        # Drop weak partial matches: keep products scoring at least half the best match.
        if terms and scored:
            floor = scored[0][0] * RELEVANCE_FLOOR
            scored = [sr for sr in scored if sr[0] >= floor]
        stock = _stock(conn, [r["product_id"] for _, r in scored])

    matches: list[ProductSummary] = []
    for _, row in scored:
        sizes = stock.get(row["product_id"], {})
        if size_u and sizes.get(size_u, 0) <= 0:
            continue
        matches.append(ProductSummary(
            product_id=row["product_id"],
            name=row["name"],
            garment_type=row["garment_type"],
            price=row["price"],
            colors=json.loads(row["colors"]),
            sizes_in_stock=[s for s, q in sizes.items() if q > 0],
        ))
        if len(matches) == limit:
            break
    for m in matches:
        ctx.deps.remember(m.product_id, prices=[m.price])
    if not matches:
        return SearchResults(matches=[], corrections=corrections, note="No exact matches. Retry once with fewer "
                             "filters or a broader query; if that is also empty, tell the customer and suggest "
                             "something close.")
    return SearchResults(matches=matches, corrections=corrections)


def get_product_details(ctx: RunContext[ChatDeps], product_id: str) -> ProductDetails:
    """Everything the shop knows about one product: description, colors, tags, price and stock per size.

    Use this to describe a product or answer "what is it made of / what does it look like" questions.

    Args:
        product_id: A product_id returned by search_products (or shown in an earlier reply).
    """
    with _connect(ctx.deps.db_path) as conn:
        row = _catalogue_row(conn, product_id)
        stock = _stock(conn, [product_id]).get(product_id, {})
    by_size = [SizeStock(size=s, quantity=q) for s, q in stock.items()]
    total = sum(stock.values())
    ctx.deps.remember(product_id, prices=[row["price"]], quantities=[*stock.values(), total])
    return ProductDetails(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        colors=json.loads(row["colors"]),
        search_tags=json.loads(row["search_tags"]),
        price=row["price"],
        stock_by_size=by_size,
        total_stock=total,
    )


def get_prices(ctx: RunContext[ChatDeps], product_ids: list[str]) -> list[PriceQuote]:
    """Exact current price (USD) for one or more products. Call this for any price question.

    Args:
        product_ids: Up to 8 product_ids returned by search_products or shown in an earlier reply.
    """
    ids = list(dict.fromkeys(product_ids))[:MAX_RESULTS]
    with _connect(ctx.deps.db_path) as conn:
        rows = [_catalogue_row(conn, pid) for pid in ids]
    for r in rows:
        ctx.deps.remember(r["product_id"], prices=[r["price"]])
    return [PriceQuote(product_id=r["product_id"], name=r["name"], price=r["price"]) for r in rows]


def check_stock(ctx: RunContext[ChatDeps], product_id: str, size: str | None = None) -> StockReport:
    """How many units of a product are in stock, for one size or across all sizes.

    Call this for any "is it in stock / how many are left / do you have it in M" question.

    Args:
        product_id: A product_id returned by search_products (or shown in an earlier reply).
        size: XS, S, M, L, XL or XXL. Leave empty for stock across all sizes.
    """
    size_u = _size(size) if size else None
    with _connect(ctx.deps.db_path) as conn:
        row = _catalogue_row(conn, product_id)
        stock = _stock(conn, [product_id]).get(product_id, {})
    total = sum(stock.values())
    quantity = stock.get(size_u, 0) if size_u else total
    ctx.deps.remember(product_id, quantities=[*stock.values(), total])
    return StockReport(
        product_id=product_id,
        name=row["name"],
        size=size_u,
        quantity=quantity,
        in_stock=quantity > 0,
        stock_by_size=[SizeStock(size=s, quantity=q) for s, q in stock.items()],
        total_stock=total,
    )


# ---------------------------------------------------------------------------
# Helpers used by agent.py
# ---------------------------------------------------------------------------

# "$68", "$68.00", "$1,234.50"
_MONEY_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{1,2}))?")
# "25 in stock", "3 left", "12 units available", "only 2 remaining"
_COUNT_RE = re.compile(r"\b(\d+)\s+(?:units?\s+|pieces?\s+|of them\s+)?(?:in stock|left|available|remaining)\b", re.I)


def _money(text: str) -> set[float]:
    return {round(float(m.group(1).replace(",", "") + "." + (m.group(2) or "0")), 2) for m in _MONEY_RE.finditer(text)}


def validate_reply(ctx: RunContext[ChatDeps], output: AgentReply) -> AgentReply:
    """Reject replies that aren't grounded in this run's tool results.

    - product_ids must have been returned by a tool (no invented products).
    - every $ amount must be a price a tool returned (or a small multiple of one, e.g. "two for $136"),
      or a number the customer typed themselves (e.g. their budget).
    - every "N in stock / left / available" count must be a quantity a tool returned.
    - page_results ids must also have been returned by a tool.
    """
    deps = ctx.deps
    problems = []

    unknown = [pid for pid in output.product_ids if pid not in deps.seen_ids]
    if unknown:
        problems.append(f"product_ids {unknown} were not returned by a tool; look them up first or remove them.")
    if output.page_results:
        unknown_page = [pid for pid in output.page_results.product_ids if pid not in deps.seen_ids]
        if unknown_page:
            problems.append(f"page_results.product_ids {unknown_page} were not returned by a tool; "
                            "only list ids from your search results.")

    allowed_money = {round(p * k, 2) for p in deps.seen_prices for k in range(1, 11)} | _money(deps.customer_text)
    bad_money = sorted(_money(output.reply) - allowed_money)
    if bad_money:
        problems.append(f"the reply quotes {['$%.2f' % m for m in bad_money]} but no tool returned that price; "
                        "call get_prices and use the exact value.")

    bad_counts = sorted({int(m.group(1)) for m in _COUNT_RE.finditer(output.reply)} - deps.seen_quantities)
    if bad_counts:
        problems.append(f"the reply states stock counts {bad_counts} that no tool returned; "
                        "call check_stock and use the exact quantity.")

    if problems:
        raise ModelRetry("Your reply is not grounded in the database: " + " ".join(problems))
    output.product_ids = list(dict.fromkeys(output.product_ids))  # drop duplicates, keep order
    if output.page_results:
        output.page_results.product_ids = list(dict.fromkeys(output.page_results.product_ids))
    return output


def load_product_cards(product_ids: list[str], db_path: Path = DB_PATH) -> list[ProductCard]:
    """Build cards straight from the DB so prices, images and stock are always the real values."""
    if not product_ids:
        return []
    marks = ",".join("?" * len(product_ids))
    with _connect(db_path) as conn:
        rows = {r["product_id"]: r for r in conn.execute(
            f"SELECT * FROM catalogue WHERE product_id IN ({marks})", product_ids)}
        stock = _stock(conn, list(rows))
    return [
        ProductCard(
            product_id=pid,
            name=rows[pid]["name"],
            garment_type=rows[pid]["garment_type"],
            price=rows[pid]["price"],
            colors=json.loads(rows[pid]["colors"]),
            image_url=f"/media/{rows[pid]['image_file_path']}",
            page_url=f"/products/{pid}",
            sizes_in_stock=[s for s, q in stock.get(pid, {}).items() if q > 0],
        )
        for pid in product_ids
        if pid in rows
    ]


def load_catalogue_products(product_ids: list[str] | None = None, db_path: Path = DB_PATH) -> list[CatalogueProduct]:
    """Full catalogue records (GET /api/products shape). None = every product, sorted by name;
    otherwise the given ids in the given order (unknown ids are skipped)."""
    with _connect(db_path) as conn:
        if product_ids is None:
            rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
        else:
            if not product_ids:
                return []
            marks = ",".join("?" * len(product_ids))
            by_id = {r["product_id"]: r for r in conn.execute(
                f"SELECT * FROM catalogue WHERE product_id IN ({marks})", product_ids)}
            rows = [by_id[pid] for pid in product_ids if pid in by_id]
        stock = _stock(conn, [r["product_id"] for r in rows])
    out = []
    for row in rows:
        inv = [InventoryItem(size=sz, quantity=q) for sz, q in stock.get(row["product_id"], {}).items()]
        out.append(CatalogueProduct(
            product_id=row["product_id"],
            name=row["name"],
            garment_type=row["garment_type"],
            description=row["description"],
            colors=json.loads(row["colors"]),
            search_tags=json.loads(row["search_tags"]),
            image_file_path=row["image_file_path"],
            image_url=f"/media/{row['image_file_path']}",
            price=row["price"],
            inventory=inv,
            total_stock=sum(i.quantity for i in inv),
        ))
    return out


# ---------------------------------------------------------------------------
# Customer memory (chat_messages). Only ever called for a logged-in user id from a valid session.
# ---------------------------------------------------------------------------

RECENT_TURNS = 20  # newest messages replayed verbatim to the model
EARLIER_HIGHLIGHTS = 10  # older customer messages summarised in the instructions
PRODUCTS_REMEMBERED = 8
WIDGET_HISTORY = 50  # messages the widget redraws on return


def _connect_rw(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ids_from_products_json(raw: str | None) -> list[str]:
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []
    return [i["product_id"] for i in items if isinstance(i, dict) and i.get("product_id")]


def _stored(row: sqlite3.Row) -> StoredMessage:
    return StoredMessage(role=row["role"], content=row["content"],
                         product_ids=_ids_from_products_json(row["products_json"]), created_at=row["created_at"])


def load_customer_memory(user: sqlite3.Row, db_path: Path = DB_PATH) -> CustomerMemory:
    """Build the agent's memory of a logged-in customer from users + chat_messages."""
    first = user["first_name"] or user["name"].split()[0]
    profile = CustomerProfile(
        user_id=user["id"], first_name=first, last_name=user["last_name"], full_name=user["name"],
        email=user["email"], member_since=user["created_at"],
    )
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, created_at FROM chat_messages WHERE user_id = ? ORDER BY id",
            (user["id"],),
        ).fetchall()
        messages = [_stored(r) for r in rows]

        # Products from past replies, newest first, de-duplicated, with current names from the catalogue.
        seen: dict[str, str] = {}
        for m in reversed(messages):
            for pid in m.product_ids:
                seen.setdefault(pid, m.created_at)
        ids = list(seen)[:PRODUCTS_REMEMBERED]
        names = {}
        if ids:
            marks = ",".join("?" * len(ids))
            names = {r["product_id"]: r["name"] for r in conn.execute(
                f"SELECT product_id, name FROM catalogue WHERE product_id IN ({marks})", ids)}

    recent = messages[-RECENT_TURNS:]
    while recent and recent[0].role != "user":  # history must start with a customer turn
        recent = recent[1:]
    older = messages[: len(messages) - len(recent)]
    return CustomerMemory(
        profile=profile,
        recent_messages=recent,
        earlier_requests=[m for m in older if m.role == "user"][-EARLIER_HIGHLIGHTS:],
        products_shown_before=[ProductMention(product_id=pid, name=names[pid], last_shown_at=seen[pid])
                               for pid in ids if pid in names],
        total_messages=len(messages),
        first_chat_at=messages[0].created_at if messages else None,
        last_chat_at=messages[-1].created_at if messages else None,
    )


def render_page_context(page: PageContext | None, db_path: Path = DB_PATH) -> str:
    """Where the customer is on the site, for the agent's instructions (Problem 9: page-aware assistant).

    The product id is checked against the catalogue so a bad or stale id from the browser is ignored."""
    if page is None:
        return "## Current page\nUnknown."
    if page.product_id:
        with _connect(db_path) as conn:
            row = conn.execute("SELECT product_id, name FROM catalogue WHERE product_id = ?",
                               (page.product_id,)).fetchone()
        if row:
            return ("## Current page\n"
                    f"The customer is viewing the product page for {row['name']} (product_id: {row['product_id']}). "
                    "\"This\", \"it\", \"this one\" or a question with no product named most likely means this product.")
    where = {"/": "the home page", "/products": "the Products page", "/about": "the About Us page"}.get(
        page.path.rstrip("/") or "/", "the website")
    return f"## Current page\nThe customer is on {where} ({page.path}). They are not viewing a specific product."


def render_customer_context(memory: CustomerMemory | None) -> str:
    """The per-request block appended to the agent's instructions (see prompt.md `customer_memory`)."""
    if memory is None:
        return "## Current customer\nGuest (not logged in). Nothing from this chat is saved."
    p = memory.profile
    lines = [
        "## Current customer (logged in)",
        f"- Name: {p.full_name} (first name: {p.first_name})",
        f"- Email: {p.email}",
        f"- Customer since: {p.member_since[:10]}",
    ]
    if memory.total_messages == 0:
        lines.append("- Past chats: none. This is their first conversation with you.")
    else:
        lines.append(f"- Past chats: {memory.total_messages} saved messages, from {memory.first_chat_at[:10]} "
                     f"to {memory.last_chat_at[:10]}. The most recent ones are in the conversation above.")
    if memory.earlier_requests:
        lines.append("- Earlier things they asked about (older than the conversation above):")
        lines += [f"  - {m.created_at[:10]}: {m.content[:160]}" for m in memory.earlier_requests]
    if memory.products_shown_before:
        lines.append("- Products you showed them before (newest first):")
        lines += [f"  - {m.name} ({m.product_id}), {m.last_shown_at[:10]}" for m in memory.products_shown_before]
    return "\n".join(lines)


def save_chat_exchange(user_id: int, message: str, reply: ChatReply, db_path: Path = DB_PATH) -> None:
    """Write the customer's message and the assistant's reply as two chat_messages rows (one transaction).

    products_json on the assistant row is a snapshot of the chat cards in the GET /api/products shape,
    matching the seed rows, so the widget can redraw them and the agent knows what "this" referred to."""
    snapshot = [p.model_dump() for p in load_catalogue_products([c.product_id for c in reply.products], db_path)]
    with _connect_rw(db_path) as conn:
        conn.execute("INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)", (user_id, message))
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply.reply, json.dumps(snapshot)),
        )
        conn.commit()


def load_chat_history(user_id: int, db_path: Path = DB_PATH) -> list[HistoryMessage]:
    """Newest saved messages, oldest first, with product cards rebuilt from the DB (current price/stock)."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM (SELECT id, role, content, products_json, created_at FROM chat_messages
                              WHERE user_id = ? ORDER BY id DESC LIMIT ?) ORDER BY id""",
            (user_id, WIDGET_HISTORY),
        ).fetchall()
    return [
        HistoryMessage(
            role=r["role"],
            content=r["content"],
            products=load_product_cards(_ids_from_products_json(r["products_json"])[:4], db_path),
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Audit trail (append-only)
# ---------------------------------------------------------------------------

AUDIT_TEXT_CHARS = 500

# Personal data that must never land in the audit log, even if a customer types it.
_REDACTIONS = [
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[redacted-card-number]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[redacted-email]"),
    (re.compile(r"\b(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b"), "[redacted-phone]"),
]


def redact(text: str | None) -> str | None:
    """Mask card numbers, emails and phone numbers, then truncate, for the audit trail."""
    if text is None:
        return None
    for pattern, mask in _REDACTIONS:
        text = pattern.sub(mask, text)
    return text[:AUDIT_TEXT_CHARS]


def _short(text: object, limit: int = 240) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _summarise_result(content: object) -> str:
    """Readable one-line summary of a tool result for the audit trail."""
    if isinstance(content, SearchResults):
        fixes = f"; corrections={content.corrections}" if content.corrections else ""
        ids = ", ".join(m.product_id for m in content.matches[:5])
        more = f" (+{len(content.matches) - 5} more)" if len(content.matches) > 5 else ""
        return f"{len(content.matches)} matches: {ids}{more}{fixes}"
    if isinstance(content, StockReport):
        return f"{content.product_id} size={content.size or 'all'} quantity={content.quantity} total={content.total_stock}"
    if isinstance(content, ProductDetails):
        return f"{content.product_id} price=${content.price:.2f} total_stock={content.total_stock}"
    if isinstance(content, list) and content and isinstance(content[0], PriceQuote):
        return "; ".join(f"{q.product_id}=${q.price:.2f}" for q in content)
    return _short(content)


def audit_steps(messages: list) -> tuple[list[AuditStep], int]:
    """Turn a run's new messages into ordered audit steps. Returns (steps, retry_count)."""
    from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart

    steps: list[AuditStep] = []
    retries = 0

    def add(**kw):
        steps.append(AuditStep(index=len(steps) + 1, **kw))

    for msg in messages:
        stamp = getattr(msg, "timestamp", None)
        at = stamp.isoformat() if stamp else None
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                if part.tool_name == "final_result":  # the structured AgentReply itself
                    add(kind="model_response", tool_name="final_result", summary="structured reply returned", at=at)
                else:
                    add(kind="tool_call", tool_name=part.tool_name, args=part.args, at=at)
            elif isinstance(part, ToolReturnPart):
                if part.tool_name != "final_result":
                    add(kind="tool_result", tool_name=part.tool_name, summary=_summarise_result(part.content),
                        at=part.timestamp.isoformat())
            elif isinstance(part, RetryPromptPart):
                retries += 1
                add(kind="retry", tool_name=part.tool_name, summary=_short(part.model_response()), at=at)
            elif isinstance(part, TextPart) and isinstance(msg, ModelResponse) and part.content.strip():
                add(kind="model_response", summary=_short(part.content), at=at)
    return steps, retries


def usage_of(usage) -> AuditUsage:
    return AuditUsage(requests=usage.requests, tool_calls=usage.tool_calls, input_tokens=usage.input_tokens,
                      output_tokens=usage.output_tokens, total_tokens=usage.total_tokens)


def append_audit_entry(entry: AuditEntry, path: Path = AUDIT_PATH) -> None:
    """Append one entry to the JSON array in `path` without touching earlier entries.

    The file is opened in append mode (never truncated on open) under an exclusive lock, so concurrent
    requests can't interleave. Only the array's closing bracket is removed and re-written after the new
    entry. If the file isn't a JSON array we refuse to modify it rather than risk wiping history."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = entry.model_dump_json(indent=2).encode("utf-8")
    with open(path, "a+b") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                f.write(b"[\n" + block + b"\n]\n")
                return
            start = max(0, size - 256)
            f.seek(start)
            tail = f.read()
            close = tail.rfind(b"]")
            if close == -1:
                raise ValueError(f"{path} does not end with a JSON array; refusing to modify it")
            before = tail[:close].rstrip()
            empty_array = before.endswith(b"[") and start == 0 and not before[:-1].strip()
            f.truncate(start + close)  # drops only the final "]" (and trailing newline)
            f.write((b"\n" if empty_array else b",\n") + block + b"\n]\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
