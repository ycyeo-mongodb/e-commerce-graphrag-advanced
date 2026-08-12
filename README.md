# LeafyShop — E-Commerce GraphRAG Advanced Workshop

Hands-on workshop repo for **LeafyShop**, a fictional e-commerce storefront powered by **MongoDB Atlas**. Build an explicit **Product Support Agent** with **Ollama** (local LLM) and MongoDB — no AWS Lambda, no LangChain, no cloud API keys required for the agent module.

Companion documentation portal: [graphrag_workshop](https://github.com/ycyeo-mongodb/e-commerce-graphrag-advanced) (workshop docs in `graphrag_workshop`).

## What you'll build

### Part 1 — Agentic AI + MongoDB (this repo, v1)

- **LeafyShop storefront** — search, cart, and catalog UI (from the GenAI e-commerce template)
- **Product Support Agent** — chat bubble backed by an explicit Python agent loop
- **Four allowlisted tools**: `search_knowledge`, `get_product`, `save_memory`, `recall_memory`
- **Educational trace** — see each tool decision and result (no hidden chain-of-thought)
- **MongoDB collections**: `products`, `knowledge_base`, `memories`

### Part 2 — RAG + Vector Search (planned)

- Add embeddings and Atlas Vector Search to `search_knowledge`
- Agent loop stays unchanged — only the tool implementation changes

### Part 3 — GraphRAG (planned)

- Knowledge graph + `$graphLookup` + hybrid retrieval for multi-hop support questions

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
# Optional: load product embeddings for search UI
python scripts/01_load_and_embed.py
python scripts/02_create_indexes.py

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

## Example support prompts

```
What is your returns policy?
Which products support vector search?
Tell me about Heritage Slip-on Athletic Sneakers
Remember that I prefer concise answers
What did you remember about me?
```

## Project structure

```
backend/
  app.py                 # FastAPI — storefront + /api/support/chat
  agent/                 # Explicit Ollama agent loop
    agent.py
    tools.py
    ollama_client.py
frontend/
  index.html             # LeafyShop UI + support chat panel
scripts/
  seed_support_data.py   # knowledge_base + memory indexes
  01_load_and_embed.py   # Product catalog (search workshop)
tests/
```

## Workshop checkpoints

| Checkpoint | Prompt | What to observe |
|------------|--------|-----------------|
| 1 | "Hello" (no DB needed) | Model can answer without tools |
| 2 | "What is your returns policy?" | `search_knowledge` tool call in trace |
| 3 | Product name + "remember concise answers" | `get_product` then `save_memory` |
| 4 | "What did you remember?" | `recall_memory` returns session note |
| 5 | Stop Ollama | Clear 503 error, no arbitrary execution |

## Tests

```bash
PYTHONPATH=backend pytest tests/ -q
```

## What to change next

- **Vector Search**: embed `knowledge_base` chunks; swap keyword search in `search_knowledge`
- **GraphRAG**: add `knowledge_graph` collection and hybrid retrieval
- **Azure AI Foundry**: replace `OllamaClient` with a provider interface — agent loop unchanged

## License

Workshop sample code — fictional data only.
