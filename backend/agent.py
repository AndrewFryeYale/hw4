"""Campus Customs chatbot: Pydantic AI agent wiring.

main.py calls `chat(request, customer)`. That builds the agent once (lazily, on the first message), replays the
widget's earlier turns as message history, runs the agent with its tools, and turns the agent's
structured AgentReply into the ChatReply the site renders: reply text, chat product cards, and (when the
customer is browsing) a page_update the front end shows on the Products page. All product data in the
response is loaded from the DB by id; the agent only chooses which ids.

Customer memory: for a logged-in customer, main.py passes a models.CustomerMemory. Its recent turns are
replayed as message history, and `current_customer` (a dynamic instruction) adds their name, email and
a summary of older conversations to the agent's context on every request. Guests get neither.

LLM calls go through Portkey (OpenAI-compatible) with the key from PORTKEY_API_KEY.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.settings import ModelSettings
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import tools
from models import AgentReply, AuditEntry, ChatReply, ChatRequest, ChatTurn, CustomerMemory, PageUpdate, StoredMessage

BACKEND_DIR = Path(__file__).resolve().parent
# PORTKEY_API_KEY may already be in the environment; otherwise read it from a .env (hw4/ or repo root).
load_dotenv(BACKEND_DIR.parent / ".env")
load_dotenv(BACKEND_DIR.parent.parent / ".env")

PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MODEL_NAME = os.environ.get("PORTKEY_MODEL", "gpt-5.6-luna")

# Sections of prompts/prompt.md joined into the system prompt, in order.
PROMPT_SECTIONS = ("guardrails", "voice", "basics", "database_lookups", "page_results", "customer_memory", "page_awareness")

# Cost / loop guardrails. Measured typical turn: 2 model requests, 1-2 tool calls, ~5-8k total tokens.
# Caps sit at roughly 3-5x that, so normal questions never hit them but a runaway loop is cut off.
MAX_REQUESTS = 6  # model round trips per customer message (normal: 2; +room for validator retries)
MAX_TOOL_CALLS = 10  # tool executions per message
MAX_TOTAL_TOKENS = 40_000  # input + output tokens per message
MAX_OUTPUT_TOKENS_PER_RESPONSE = 1_000  # per model response (largest seen: ~450, a 27-id page list)
CHAT_LIMITS = UsageLimits(request_limit=MAX_REQUESTS, tool_calls_limit=MAX_TOOL_CALLS, total_tokens_limit=MAX_TOTAL_TOKENS)
MODEL_SETTINGS = ModelSettings(max_tokens=MAX_OUTPUT_TOKENS_PER_RESPONSE)
LIMITS = {"request_limit": MAX_REQUESTS, "tool_calls_limit": MAX_TOOL_CALLS, "total_tokens_limit": MAX_TOTAL_TOKENS,
          "max_output_tokens_per_response": MAX_OUTPUT_TOKENS_PER_RESPONSE}

LIMIT_FALLBACK = ("Sorry, that one took me too many steps to answer. Could you ask a bit more simply, like "
                  "\"Do you have the Yale Mom Crewneck in medium?\" or \"Show me hoodies under $70\"?")

# The model provider's own safety filter (Azure via Portkey) can reject a message outright, e.g. jailbreak
# attempts. That's a second guardrail layer working, so answer politely instead of erroring.
FILTERED_FALLBACK = ("I can only help with Campus Customs shopping: products, sizes, prices and stock. "
                     "What can I help you find today?")

logger = logging.getLogger("campus_customs.agent")


def build_model() -> OpenAIChatModel:
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=os.environ["PORTKEY_API_KEY"])
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def get_chat_agent() -> Agent[tools.ChatDeps, AgentReply]:
    """Build the agent once per server process; reused by every chat request."""
    agent = Agent(
        build_model(),
        deps_type=tools.ChatDeps,
        output_type=AgentReply,
        system_prompt=[tools.load_prompt(s) for s in PROMPT_SECTIONS],
        tools=[tools.search_products, tools.get_product_details, tools.get_prices, tools.check_stock],
        model_settings=MODEL_SETTINGS,
        retries=2,
    )
    agent.output_validator(tools.validate_reply)

    @agent.instructions
    def current_customer(ctx: RunContext[tools.ChatDeps]) -> str:
        # Re-evaluated on every request: who is chatting (name, email) and what they discussed before.
        return tools.render_customer_context(ctx.deps.customer)

    @agent.instructions
    def current_page(ctx: RunContext[tools.ChatDeps]) -> str:
        # Which page / product the customer has open, so "is this in medium?" resolves (Problem 9).
        return tools.render_page_context(ctx.deps.page, ctx.deps.db_path)

    return agent


def to_message_history(history: list[ChatTurn] | list[StoredMessage]) -> list[ModelMessage]:
    """Widget turns or saved chat_messages rows -> Pydantic AI messages (user = request, assistant = response)."""
    messages: list[ModelMessage] = []
    for turn in history:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            text = turn.content
            if turn.product_ids:
                cards = ", ".join(f"{i}. {pid}" for i, pid in enumerate(turn.product_ids, 1))
                text += f"\n\n[Product cards shown, in order: {cards}]"
            messages.append(ModelResponse(parts=[TextPart(content=text)]))
    return messages


async def chat(request: ChatRequest, customer: CustomerMemory | None = None) -> ChatReply:
    """Answer one message. `customer` is the logged-in customer's memory (from main.py's session lookup),
    or None for a guest. Logged-in history comes from the DB; a guest's comes from the widget.

    Every call appends one AuditEntry to output/audit_trail.json, whether it succeeds, hits a cap or fails."""
    history = customer.recent_messages if customer else request.history
    customer_text = "\n".join([*(t.content for t in history if t.role == "user"), request.message])
    deps = tools.ChatDeps(customer=customer, customer_text=customer_text, page=request.page)
    started, t0 = datetime.now(timezone.utc), time.perf_counter()
    audit = dict(outcome="ok", error=None, usage=None, reply=None)
    result = None
    try:
        with capture_run_messages() as run_messages:
            try:
                result = await get_chat_agent().run(
                    request.message,
                    message_history=to_message_history(history),
                    deps=deps,
                    usage_limits=CHAT_LIMITS,
                )
            except UsageLimitExceeded as exc:
                # Guardrail hit: don't 502 the customer, give a friendly nudge and log it.
                audit.update(outcome="limit_exceeded", error=str(exc))
                reply = ChatReply(reply=LIMIT_FALLBACK)
                audit["reply"] = reply.reply
                return reply
            except ModelHTTPError as exc:
                if "content_filter" not in str(exc.body):
                    audit.update(outcome="error", error=f"{type(exc).__name__}: {exc}")
                    raise
                audit.update(outcome="content_filtered", error="provider content filter rejected the message")
                reply = ChatReply(reply=FILTERED_FALLBACK)
                audit["reply"] = reply.reply
                return reply
            except Exception as exc:
                audit.update(outcome="error", error=f"{type(exc).__name__}: {exc}")
                raise
        reply = _to_chat_reply(result.output, request, deps)
        audit["reply"] = reply.reply
        return reply
    finally:
        _record_audit(request, customer, history, started, t0, audit, run_messages, result)


def _to_chat_reply(out: AgentReply, request: ChatRequest, deps: tools.ChatDeps) -> ChatReply:
    page_update = None
    if out.page_results:
        # Agent picked the ids; the full product records come from the DB, never from the model.
        page_update = PageUpdate(
            title=out.page_results.title,
            query=request.message,
            products=tools.load_catalogue_products(out.page_results.product_ids, deps.db_path),
        )
    return ChatReply(
        reply=out.reply,
        products=tools.load_product_cards(out.product_ids, deps.db_path),
        page_update=page_update,
    )


def _record_audit(request, customer, history, started, t0, audit, run_messages, result) -> None:
    """Append this run to the audit trail. Never lets an audit problem break the customer's chat."""
    try:
        new_messages = run_messages[len(history):]  # skip replayed history; keep only this run's loop
        steps, retries = tools.audit_steps(new_messages)
        usage = tools.usage_of(result.usage) if result else tools.AuditUsage(
            requests=sum(1 for m in new_messages if m.kind == "response"),
            tool_calls=sum(1 for s in steps if s.kind == "tool_call"),
        )
        out = result.output if result else None
        tools.append_audit_entry(AuditEntry(
            run_id=str(uuid.uuid4()),
            timestamp=started.isoformat(),
            customer="logged_in" if customer else "guest",
            user_id=customer.profile.user_id if customer else None,
            page_path=request.page.path if request.page else None,
            page_product_id=request.page.product_id if request.page else None,
            message=tools.redact(request.message),
            history_turns=len(history),
            model=MODEL_NAME,
            prompt_sections=list(PROMPT_SECTIONS),
            limits=LIMITS,
            steps=steps,
            retries=retries,
            usage=usage,
            outcome=audit["outcome"],
            error=audit["error"],
            reply=tools.redact(audit["reply"]),
            product_ids=out.product_ids if out else [],
            page_title=out.page_results.title if out and out.page_results else None,
            page_result_count=len(out.page_results.product_ids) if out and out.page_results else 0,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        ))
    except Exception:
        logger.exception("could not write audit entry")
