# Campus Customs: Website + AI Shopping Assistant (HW4)

A customer-facing store for **Campus Customs** (Yale apparel, 57 Broadway, New Haven) with an AI chat
assistant. It's a React + Vite + TypeScript front end, a FastAPI backend, and a **Pydantic AI** agent that
answers from the real catalogue and inventory, puts search results on the page, and remembers
logged-in customers.

## 1. Place the data pack (not in git)

The database and product images are provided separately and are **not** in this repo. Put them here:

```
hw4/
└── data/
    ├── campus_customs.db
    └── products/          # images referenced by the catalogue (image_file_path = products/<name>.jpg)
```

The backend reads `data/campus_customs.db` relative to the repo, so no path config is needed. On first
start it adds a small `sessions` table for logins.

## 2. Configure the API key

```bash
cp .env.example .env       # then put your Portkey key in .env
```
LLM calls go through **Portkey** (`https://api.portkey.ai/v1`) using `PORTKEY_API_KEY`, model
`gpt-5.6-luna`. The key can also come from your shell environment, or from a `.env` one folder up.

## 3. Run the back end (FastAPI, port 8000)

```bash
cd hw4
python3 -m venv venv
venv/bin/pip install -r requirements.txt

cd backend
../venv/bin/uvicorn main:app --reload --port 8000
```
Check it: `curl localhost:8000/api/health` → `{"status":"ok"}`.

## 4. Run the front end (Vite, port 5173)

In a second terminal:
```bash
cd hw4/frontend
npm install
npm run dev
```
Open **http://localhost:5173**. Vite proxies `/api` and `/media` to the backend on :8000, so start the
backend first.

**Test login (seed data):** `test@campuscustoms.yale.edu` / `password`

## Try it
- Ask the chat **"What hoodies are available?"**: it answers and fills the Products page with the matches.
- Open any product and ask **"How many do you have in medium?"**: it checks live stock for that item.
- Log in, chat, refresh: your conversation and the assistant's memory of you persist.

## Project layout

```
hw4/
├── AI_prompts.md            # every prompt used to build this, by problem
├── requirements.txt         # Python deps (pinned)
├── .env.example             # placeholders only
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app: run with `uvicorn main:app --reload --port 8000` from backend/
│   ├── agent.py             # Pydantic AI agent wiring (model, prompts, tools, limits, audit)
│   ├── tools.py             # tools the agent calls (search, details, prices, stock) + memory/audit helpers
│   ├── models.py            # Pydantic types: API contract, tool results, memory, audit entries
│   ├── auth.py              # password hashing + login sessions
│   └── prompts/prompt.md    # system prompts (guardrails, voice, rules, …)
└── output/
    ├── harness.md           # how the system works: specs, models, tools, safety, audit (start here)
    ├── design.md            # storefront design choices
    ├── usability.md         # Problem 9 improvements
    ├── app_check.html       # live-site test report (open in a browser)
    ├── app_check_images/    # screenshots linked from app_check.html
    └── audit_trail.json     # append-only log of every agent run
```

The agent itself is four files under `backend/`: `prompts/prompt.md`, `agent.py`, `tools.py`, `models.py`.
See **`output/harness.md`** for the full specs (loop limits, token caps, result caps, safety rules).
