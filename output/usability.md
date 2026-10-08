# Usability & Agent Improvements — HW4 Problem 9

Four improvements: two to the front end and two to the agent/backend. Each one is live in the final app
(`uvicorn main:app --reload --port 8000` from `backend/`, `npm run dev` in `frontend/`) and was checked in
headless Chrome against the running site.

| # | Type | Improvement | Where you see it |
|---|---|---|---|
| 1 | Front end | Filter & sort toolbar on the Products page | Products page, also on chat results |
| 2 | Front end | Context-aware quick-reply chips + "Ask our assistant about this item" | Chat window, every single-item page |
| 3 | Agent / backend | Page-aware assistant: knows what the customer is looking at | Ask "how much is it?" on any product page |
| 4 | Agent / backend | Better search: relevance ranking + typo tolerance | Ask for a college ("saybruk college") or a specific style |

---

## 1. Front end — Filter & sort toolbar on the Products page

### What I added
- `frontend/src/components/ProductBrowser.tsx`, used by `pages/Products.tsx` for **both** the full
  catalogue and chat search results (Problem 7). It has:
  - **Search box**: filters as you type, over name, garment type, description, colors and tags (every
    word must match, e.g. "gray morse").
  - **Category chips with counts**: Hoodies (27), Quarter-zips (11), Jackets & fleece (8), Crewnecks (30),
    Tees & shirts (26). The 22 messy `garment_type` values in the DB are grouped into categories shoppers
    recognise. Chips only appear for categories that exist in the current list.
  - **Sort**: Featured, Price low→high, Price high→low, Name A–Z.
  - **In stock only** toggle (`total_stock > 0`).
  - **"Showing N of M"** count, **Clear filters**, and an empty state that points to the chat assistant.
- Filters reset when a new chat search replaces the results (the component is keyed by the search).
- Cards are still the Problem 3 `ProductCard`, so clicking one opens the single-item page as before.

### Why it improves the experience
Before, the Products page was one unsorted grid of **102** products. To find "a gray hoodie under $50" you
had to scroll through all of it or open the chat. Now the common shopping moves (narrow by type, sort by
price, hide sold-out items, type a keyword) take one click each and update instantly, without waiting for
the AI. It also makes chat results more useful: after the assistant puts 27 hoodies on the page, the
customer can sort them by price or hide the sold-out ones.

### Verified
All 102 → Hoodies chip **27** → sorted ascending ($45 … $88) → + "gray" **10** → nonsense text shows the
empty state → Clear filters → back to **102**.

---

## 2. Front end — Context-aware quick replies + "Ask our assistant about this item"

### What I added
- **Suggestion chips** above the chat input (`components/ChatWidget.tsx`, `suggestionsFor()`). One tap
  sends the question. They change with the page:
  - On a product page: *What sizes are in stock?* · *Tell me more about this* · *Show me similar items*
  - On the Products page: *What hoodies do you have?* · *Gifts under $50* · *Anything in XXL?*
  - Elsewhere: *Show me crewnecks* · *Gift ideas for a Yale parent* · *What's under $40?*
  - Hidden while the assistant is thinking, so nothing gets double-sent.
- **"Ask our assistant about this item"** button on every single-item page (`pages/ProductDetail.tsx`).
  It opens the chat through a tiny event helper (`src/chatEvents.ts`, `openChat()`), so any page can
  open the chat without wiring props through the app.
- Small fix in the same area: assistant messages now render `**bold**` as bold. Some seed chat history
  (Problem 8) showed raw asterisks.

### Why it improves the experience
An empty chat box is a blank-page problem: customers don't know what the bot can do or how to phrase
things. The chips show what it's good at (stock, sizes, gifts, budgets) and get a useful answer in one tap,
which matters most on phones where typing is slow. On a product page the most likely questions are about
*that* product, so those are offered. The button puts help right next to the size picker, where shoppers
actually get stuck, instead of only in a corner bubble.

### Verified
On `/products/morse-1-4-zip`: the button opens the chat → chips show the product-page set → tapping
*What sizes are in stock?* answers "XS (15), S (2), M (8), XL (25), and XXL (2). L is currently sold
out", which matches `inventory` exactly.

---

## 3. Agent / backend — Page-aware assistant (knows what you're looking at)

### What I added
- **API contract:** `ChatRequest` has an optional `page: PageContext { path, product_id }`
  (`backend/models.py`). The widget sends the current path, and the product id when on
  `/products/:productId` (`frontend/src/api.ts` `sendChat(..., page)`).
- **Agent context:** a second dynamic instruction in `backend/agent.py`:
  ```python
  @agent.instructions
  def current_page(ctx): return tools.render_page_context(ctx.deps.page, ctx.deps.db_path)
  ```
  `tools.render_page_context()` **looks the product id up in the catalogue**. A bad or stale id from the
  browser is ignored ("not viewing a specific product") instead of being trusted. On a product page the
  model sees: *"The customer is viewing the product page for Morse 1 4 Zip (product_id: morse-1-4-zip).
  'This', 'it', 'this one' … most likely means this product."*
- **Prompt:** new `## page_awareness` section in `prompts/prompt.md`. Resolve "this/it" to the viewed
  product and call `check_stock` / `get_prices` / `get_product_details` with its id directly; "similar
  items" → search the same style and show them with `page_results`; facts still come only from tools.

### Why it makes the site better
Customers ask about what's in front of them: "does it come in medium?", "how much is it?". Before, the
agent had no idea what "it" was. It had to ask, or search and guess, which is slow and sometimes wrong.
Now those questions get a direct, correct answer, and the agent skips a search step (fewer LLM round
trips, so faster and cheaper). It works with improvement 2: the product-page chips ("Tell me more about
this") only work because the agent knows what "this" is.

### Verified
- On the Morse 1/4 Zip page: "how much is it?" → "$72" (DB: 72.0). "What sizes are in stock?" → exact
  per-size counts.
- API with `page.product_id = yale-mom-crewneck`: "does it come in medium?" → "Yes … with 12 in stock"
  (DB: M = 12).
- A fake product id → rendered as "not viewing a specific product" (ignored safely).

---

## 4. Agent / backend — Better product search (relevance ranking + typo tolerance)

### What I added (all in `tools.search_products`, `backend/tools.py`)
- **Relevance ranking (IDF weighting).** Each query word is weighted by how *rare* it is in the catalogue
  (`_idf`). "saybrook" (3 products) outweighs "college" (30). A word in the product **name** counts 1.5×.
  Matches scoring under **50% of the best match** are dropped (`RELEVANCE_FLOOR`), so weak partial
  matches no longer flood the results.
- **Typo tolerance.** Misspelled words are swapped for the closest catalogue word (`difflib`, cutoff 0.8,
  built from a cached vocabulary of every word in names, types, colors, tags and descriptions):
  "davenprt" → "davenport", "crewnek" → "crewneck", "bulldgo" → "bulldog". Words that already appear
  inside a catalogue word ("zip", "hood") are never "corrected".
- `SearchResults.corrections` (new field in `models.py`) reports the fixes to the agent. The prompt says
  to answer with the corrected item and never point out the customer's spelling.

### Why it makes the site better
The trace showed a real problem. "Saybrook College" returned **30** results, because "college" matches
almost every residential-college item. That's what got put on the Products page and what the model had
to read through (tokens = cost and latency). Now the agent gets exactly the right products, so the page
updates from Problem 7 show what the customer asked for. Typo tolerance is a safety net: the LLM fixes
common words itself ("hoody" → "hoodie"), but it can't always fix proper nouns. The tool now handles
those too.

### Verified (same queries, before → after)
| Query | Before | After |
|---|---|---|
| Saybrook College | 30 (incl. Davenport, Grace Hopper…) | **3**: exactly the 3 Saybrook products in the DB |
| Timothy Dwight College | 30 | **1**: Timothy Dwight College Crewneck |
| davenprt crewnek | 29 | **1**: Davenport College Crewneck (2 typos fixed) |
| bulldog t-shirt | 30, crewnecks ranked first | 10, **Yale Bowl T Shirt** (the only bulldog tee) ranked first |
| hoodie / crewneck / hockey / gift for dad | 27 / 29 / 5 / 3 | 27 / 29 / 5 / 3 (unchanged, no regressions) |

Live via `/api/chat`: "anything from saybruk college?" → "I found 3 Saybrook College items and put them
all on the Products page", with page update "Saybrook College Gear" (3 products). "What hoodies are
available?" still → 27.

---

## Files touched
- **Front end:** `components/ProductBrowser.tsx` (new), `pages/Products.tsx`,
  `components/ChatWidget.tsx`, `pages/ProductDetail.tsx`, `chatEvents.ts` (new), `api.ts`, `index.css`.
- **Backend:** `models.py` (`PageContext`, `ChatRequest.page`, `SearchResults.corrections`), `tools.py`
  (`render_page_context`, `_idf`, `_vocabulary`, `_correct_typos`, ranking), `agent.py` (`current_page`
  instruction, `page_awareness` prompt section), `prompts/prompt.md` (`## page_awareness`).
- All browser and API tests ran as a guest, so nothing was written to `chat_messages` (still the 22 seed
  rows).
