"""Pydantic structured types for the Campus Customs chatbot.

API / agent output:
    ChatRequest     - what the site's chat widget POSTs to /api/chat.
    AgentReply      - the structured output the agent must return (text + product ids it recommends).
    ProductCard     - a product the widget renders as a small card under a reply.
    ChatReply       - what /api/chat sends back: the reply text, its product cards and an optional page update.
    PageResults     - (agent output) "show these matches on the page": a title + product ids.
    PageUpdate      - (API response) the same matches as full CatalogueProducts the Products page renders.
    CatalogueProduct - one product in the exact shape GET /api/products returns.

Audit trail (output/audit_trail.json, append-only):
    AuditEntry      - one chat request's agent loop: who/where, every step, usage, limits, outcome, output.

Tool return types (what each tool in tools.py hands back to the model, all read from campus_customs.db):
    SearchResults   - search_products      -> list of ProductSummary
    ProductDetails  - get_product_details  -> description, colors, tags, price, stock per size
    PriceQuote      - get_prices           -> exact price per product
    StockReport     - check_stock          -> units in stock, per size or in total
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MAX_CARDS = 4
MAX_REPLY_CHARS = 1200
MAX_PAGE_RESULTS = 30


class ChatTurn(BaseModel):
    """One earlier message in the conversation, as the widget holds it."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)
    # Assistant turns: ids of the product cards shown under that reply, in order, so "the first one" resolves.
    product_ids: list[str] = Field(default_factory=list, max_length=MAX_CARDS)


class PageContext(BaseModel):
    """Where the customer is on the site when they send a message (Problem 9: page-aware assistant)."""

    path: str = Field(default="/", max_length=200)  # e.g. "/products/yale-mom-crewneck"
    product_id: str | None = Field(default=None, max_length=120)  # set on a single-item page


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    page: PageContext | None = None
    # Earlier turns, oldest first, so the agent can follow up on "this one" / "in pink?".
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class PageResults(BaseModel):
    """Agent output: put these search matches on the site's Products page."""

    title: str = Field(max_length=80, description='Short heading for the page, e.g. "Hoodies" or "Gifts under $50".')
    product_ids: list[str] = Field(
        min_length=1,
        max_length=MAX_PAGE_RESULTS,
        description="Every matching product_id from your search, in the order to show them.",
    )


class AgentReply(BaseModel):
    """Structured output the agent returns. Cards are built from the DB, never from the model's text."""

    reply: str = Field(
        max_length=MAX_REPLY_CHARS,  # guardrail: an over-long reply fails validation and the model must shorten it
        description="What to say to the customer: short, friendly, plain text (no Markdown).",
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_CARDS,
        description=f"product_id of each product to show as a card, best first (0-{MAX_CARDS}). "
        "Only ids returned by a tool in this conversation.",
    )
    page_results: PageResults | None = Field(
        default=None,
        description="Set when the customer is browsing or asking what's available (a list of matches), so the "
        "site's Products page shows them. Leave null for questions about one specific product.",
    )


class SizeStock(BaseModel):
    size: str  # XS, S, M, L, XL, XXL
    quantity: int  # units on hand (inventory.quantity); 0 = sold out in that size


# ---------------------------------------------------------------------------
# Tool return types. Every value comes straight from campus_customs.db.
# ---------------------------------------------------------------------------


class ProductSummary(BaseModel):
    """One search hit: enough to pick products, not enough to quote stock counts (use check_stock)."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    sizes_in_stock: list[str]


class SearchResults(BaseModel):
    matches: list[ProductSummary]
    # Typo fixes applied to the query, e.g. {"crewnek": "crewneck"} (Problem 9: typo-tolerant search).
    corrections: dict[str, str] = Field(default_factory=dict)
    note: str | None = None  # guidance when nothing matched


class ProductDetails(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    search_tags: list[str]
    price: float
    stock_by_size: list[SizeStock]
    total_stock: int


class PriceQuote(BaseModel):
    product_id: str
    name: str
    price: float  # USD, catalogue.price


class StockReport(BaseModel):
    product_id: str
    name: str
    size: str | None  # the size asked about, or None for "any size"
    quantity: int  # units in that size, or total units across sizes when size is None
    in_stock: bool
    stock_by_size: list[SizeStock]
    total_stock: int


class ProductCard(BaseModel):
    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    image_url: str  # served by FastAPI under /media/products/...
    page_url: str  # the product's page on the site, e.g. /products/<product_id>
    sizes_in_stock: list[str]


class InventoryItem(BaseModel):
    size: str
    quantity: int


class CatalogueProduct(BaseModel):
    """Same shape as GET /api/products and the front end's `Product` type, so the site's ProductCard
    component can render chat search results without any conversion."""

    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    search_tags: list[str]
    image_file_path: str
    image_url: str
    price: float
    inventory: list[InventoryItem]
    total_stock: int


class PageUpdate(BaseModel):
    """API response: tells the front end to show these products on the Products page."""

    title: str
    query: str  # the customer message that produced these results
    products: list[CatalogueProduct]


class ChatReply(BaseModel):
    reply: str
    products: list[ProductCard] = Field(default_factory=list)
    page_update: PageUpdate | None = None


# ---------------------------------------------------------------------------
# Customer memory (logged-in customers only). Stored in chat_messages, read back by tools.py.
# ---------------------------------------------------------------------------


class CustomerProfile(BaseModel):
    """The customer fields the agent sees. Deliberately excludes password_hash and sessions."""

    user_id: int
    first_name: str
    last_name: str | None
    full_name: str
    email: str
    member_since: str  # users.created_at (UTC)


class StoredMessage(BaseModel):
    """One chat_messages row, as the agent's memory uses it."""

    role: Literal["user", "assistant"]
    content: str
    product_ids: list[str] = Field(default_factory=list)  # from products_json (assistant rows)
    created_at: str


class ProductMention(BaseModel):
    product_id: str
    name: str
    last_shown_at: str


class CustomerMemory(BaseModel):
    """Everything the agent is given about a returning customer for one chat request."""

    profile: CustomerProfile
    recent_messages: list[StoredMessage]  # newest turns, replayed verbatim as message history
    earlier_requests: list[StoredMessage]  # older customer messages (outside the replay window), summarised
    products_shown_before: list[ProductMention]  # distinct products from past replies, newest first
    total_messages: int
    first_chat_at: str | None
    last_chat_at: str | None


class HistoryMessage(BaseModel):
    """GET /api/chat/history: a saved message as the chat widget renders it."""

    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    created_at: str


# ---------------------------------------------------------------------------
# Audit trail: one AuditEntry per /api/chat request, appended to output/audit_trail.json (never rewritten).
# ---------------------------------------------------------------------------


class AuditStep(BaseModel):
    """One step of the agent loop, in order."""

    index: int
    kind: Literal["model_response", "tool_call", "tool_result", "retry"]
    tool_name: str | None = None
    args: dict | str | None = None  # tool_call: the arguments the model chose
    summary: str | None = None  # tool_result / retry / model text, shortened
    at: str | None = None  # UTC timestamp from the message


class AuditUsage(BaseModel):
    requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class AuditEntry(BaseModel):
    run_id: str
    timestamp: str  # UTC ISO-8601, when the request started
    endpoint: str = "/api/chat"
    customer: Literal["guest", "logged_in"]
    user_id: int | None = None  # id only: no name/email in the log
    page_path: str | None = None
    page_product_id: str | None = None
    message: str  # customer's message, truncated
    history_turns: int  # earlier turns given to the model
    model: str
    prompt_sections: list[str]
    limits: dict[str, int]  # the caps in force for this run
    steps: list[AuditStep] = Field(default_factory=list)
    retries: int = 0  # tool / output-validator retries (ModelRetry)
    usage: AuditUsage = Field(default_factory=AuditUsage)
    outcome: Literal["ok", "limit_exceeded", "content_filtered", "error", "rate_limited"]
    error: str | None = None
    reply: str | None = None  # truncated
    product_ids: list[str] = Field(default_factory=list)
    page_title: str | None = None
    page_result_count: int = 0
    latency_ms: int
