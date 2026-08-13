# LeafyShop — RAG, GraphRAG, and Agentic AI on MongoDB

Hands-on app for engineers learning **Agentic AI**, **RAG**, and **GraphRAG** on **MongoDB Atlas**. LeafyShop is the demo vehicle (fictional store + Product Support Agent). No LangChain. No AWS Lambda required for the agent.

Companion portal: `graphrag_workshop/` (see `workshop_plan.md` for the curriculum).

## Learning outcomes

| Outcome | What you build | MongoDB |
|---------|----------------|---------|
| **RAG** | `$vectorSearch` on support articles | `knowledge_base` + Atlas vector index |
| **Agentic AI** | Explicit Ollama tool loop + memory | `user_profiles`, `orders`, `conversations`, `memories` |
| **GraphRAG** | `$graphLookup` hybrid retrieval | `knowledge_graph` |

## What is in this repo today

### Part 1 — RAG (labs to scaffold)

- Embed `knowledge_base`, define Atlas vector index, `$vectorSearch` in `search_knowledge`

### Part 2 — Agentic AI + MongoDB (implemented)

- LeafyShop storefront (Hybrid RRF product search is **background**, not a lab)
- Product Support Agent — allowlisted tools, Agent trace, Live MongoDB inspector
- Memory layer keyed by `demo_user` (Alex, no password)

### Part 3 — GraphRAG (planned labs)

- Knowledge graph + `$graphLookup` + hybrid with vector search

## Quick start

```bash
git clone https://github.com/ycyeo-mongodb/e-commerce-graphrag-advanced.git
cd e-commerce-graphrag-advanced

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cp .env.example .env
# Edit MONGODB_URI and VOYAGE_API_KEY (for product search)

ollama pull llama3.2

python scripts/seed_support_data.py
python scripts/seed_user_profile.py   # demo_user profile + sample orders + long-term memory
# Optional: load product embeddings for search UI
python scripts/answers/01_load_and_embed.py
python scripts/answers/02_create_indexes.py

cd backend && uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 — use the green chat bubble for **Product Support Agent**.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `MONGODB_URI` | Yes | Atlas or local MongoDB |
| `VOYAGE_API_KEY` | For search UI | Product vector/text search |
| `OLLAMA_HOST` | Yes (agent) | Default `http://localhost:11434` |
| `OLLAMA_MODEL` | Yes (agent) | Default `llama3.2` |
| `BEDROCK_API_URL` | No | Legacy; not used by support agent |

## Memory layer (MongoDB)

| Layer | Collection | What it stores |
|-------|------------|----------------|
| **Short-term** | `conversations` | Last N chat turns per `user_id` + `session_id` (loaded into agent context) |
| **Session** | `memories` (`memory_scope: session`) | Notes for the current browser session |
| **Long-term** | `memories` (`memory_scope: long_term`) | Explicit preferences the customer asks you to remember |
| **Profile** | `user_profiles` | Sizes, interests, favorite brands, recently viewed products |
| **Purchase history** | `orders` | Checkout history keyed by `user_id` |

Workshop attendees sign in as **`demo_user`** (Alex Chen) — no password. Shop, checkout, then ask the agent for personalized recommendations.

## Example support prompts

```
What is your returns policy?
What have I bought before?
Recommend something based on my interests
Remember that I prefer concise answers
What did you remember about me?
```

## Project structure

```
backend/
  app.py                 # FastAPI — storefront + /api/support/chat
  catalog_browse.py      # Lab: GET /api/products (home grid + sidebar)
  agent/
    agent.py
    tools.py             # Lab: catalog + memory tools (empty TODOs)
    retrieval_starter.py # Lab: $vectorSearch for policy chat
    ollama_client.py
frontend/
  index.html             # LeafyShop UI + support chat panel
scripts/
  seed_support_data.py
  seed_user_profile.py
  TO-DO/                 # Ingest + index labs
  answers/               # catalog_browse.py, tools.py, retrieval_starter.py, 01–12
tests/
```

## Workshop checkpoints

| Checkpoint | Prompt | What to observe |
|------------|--------|-----------------|
| 1 | Shop + add to cart + checkout | Order saved to `orders` with `user_id: demo_user` |
| 2 | "What have I bought before?" | `get_purchase_history` tool in trace |
| 3 | "Recommend based on my interests" | `get_user_profile` + personalized answer |
| 4 | "Remember that I prefer concise answers" | `save_memory` → `memories` long_term |
| 5 | "What is your returns policy?" | `search_knowledge` tool call in trace |
| 6 | Follow-up in same session | Short-term memory from `conversations` |

## Tests

```bash
PYTHONPATH=backend pytest tests/ -q
```

## What to change next

- **Vector Search**: embed `knowledge_base` chunks; `$vectorSearch` in `search_knowledge`
- **GraphRAG**: add `knowledge_graph` collection and hybrid retrieval
- **Azure AI Foundry**: replace `OllamaClient` with a provider interface — agent loop unchanged

## License

Workshop sample code — fictional data only.
