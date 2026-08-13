"""
Step 8: Shopping Assistant Agent — conversational product search with tool use.

Uses Claude 4.5 Haiku's tool-calling capability to search products,
get details, and compare items through natural conversation.

Usage:
    python 08_shopping_assistant.py
"""

import os
import json

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import requests

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
db = client["workshop"]
collection = db["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
BEDROCK_API_URL = os.environ["BEDROCK_API_URL"]

TOOLS = [
    {
        "name": "search_products",
        "description": (
            "Search the product catalog using hybrid search (vector + text). "
            "Returns top 5 matching products with name, price, category, and relevance score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
                "max_price": {
                    "type": "number",
                    "description": "Optional maximum price filter",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_product_details",
        "description": "Get full details for a specific product by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "The MongoDB ObjectId of the product",
                }
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "compare_products",
        "description": "Compare two or more products side by side by their IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of product ObjectIds to compare",
                }
            },
            "required": ["product_ids"],
        },
    },
]

SYSTEM_PROMPT = (
    "You are a helpful shopping assistant for an e-commerce store with 1,000+ products. "
    "Use the provided tools to search products and answer questions. "
    "Always ground your answers in real product data — never make up products. "
    "When showing products, include the product ID so the user can ask follow-ups. "
    "Be concise but helpful."
)


def hybrid_search(query: str, category: str = None, max_price: float = None, limit: int = 5):
    """Hybrid search (vector + text + RRF) — reuses the same pipeline from Part 1."""
    query_vector = vo.embed([query], model="voyage-4-large", input_type="query").embeddings[0]

    vs_stage = {
        "$vectorSearch": {
            "index": "vector_index",
            "path": "description_embedding",
            "queryVector": query_vector,
            "numCandidates": 100,
            "limit": 30,
        }
    }
    vector_results = list(collection.aggregate([
        vs_stage,
        {"$addFields": {"vs_score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"description_embedding": 0}},
    ]))

    text_results = list(collection.aggregate([
        {"$search": {"index": "text_search_index", "text": {"query": query, "path": ["name", "description"]}}},
        {"$addFields": {"ts_score": {"$meta": "searchScore"}}},
        {"$project": {"description_embedding": 0}},
        {"$limit": 30},
    ]))

    k = 60
    rrf, doc_map = {}, {}
    for rank, doc in enumerate(vector_results):
        did = str(doc["_id"])
        rrf[did] = rrf.get(did, 0) + 1 / (k + rank + 1)
        doc_map[did] = doc
    for rank, doc in enumerate(text_results):
        did = str(doc["_id"])
        rrf[did] = rrf.get(did, 0) + 1 / (k + rank + 1)
        doc_map[did] = doc

    sorted_ids = sorted(rrf, key=lambda x: rrf[x], reverse=True)

    results = []
    for did in sorted_ids:
        doc = doc_map[did]
        if category and category.lower() not in doc.get("category", "").lower():
            continue
        if max_price and doc.get("price", 0) > max_price:
            continue
        doc["_id"] = str(doc["_id"])
        doc["score"] = round(rrf[did], 6)
        results.append(doc)
        if len(results) >= limit:
            break
    return results


def execute_tool(tool_name: str, tool_input: dict):
    """Execute a tool and return the result."""
    if tool_name == "search_products":
        results = hybrid_search(
            query=tool_input["query"],
            category=tool_input.get("category"),
            max_price=tool_input.get("max_price"),
        )
        return [
            {
                "id": r["_id"],
                "name": r.get("name", ""),
                "price": r.get("price", 0),
                "category": r.get("category", ""),
                "brand": r.get("brand", ""),
                "description": r.get("description", "")[:150],
                "score": r.get("score", 0),
            }
            for r in results
        ]

    elif tool_name == "get_product_details":
        doc = collection.find_one(
            {"_id": ObjectId(tool_input["product_id"])},
            {"description_embedding": 0},
        )
        if not doc:
            return {"error": "Product not found"}
        doc["_id"] = str(doc["_id"])
        return doc

    elif tool_name == "compare_products":
        products = []
        for pid in tool_input["product_ids"]:
            doc = collection.find_one(
                {"_id": ObjectId(pid)},
                {"description_embedding": 0},
            )
            if doc:
                doc["_id"] = str(doc["_id"])
                products.append(doc)
        return products

    return {"error": f"Unknown tool: {tool_name}"}


def chat(user_message: str, conversation_history: list) -> str:
    """Send a message and handle the tool-use loop."""
    conversation_history.append({"role": "user", "content": user_message})

    max_iterations = 5
    for _ in range(max_iterations):
        response = requests.post(
            BEDROCK_API_URL,
            json={
                "action": "converse",
                "messages": conversation_history,
                "tools": TOOLS,
                "system": SYSTEM_PROMPT,
                "max_tokens": 1000,
            },
            timeout=30,
        )
        result = response.json()

        if result.get("stop_reason") == "tool_use":
            tool_calls = [b for b in result.get("content", []) if b.get("type") == "tool_use"]
            conversation_history.append({"role": "assistant", "content": result["content"]})

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc["input"]
                tool_id = tc["id"]

                print(f"   🔧 {tool_name}({json.dumps(tool_input, ensure_ascii=False)[:80]})")
                tool_result = execute_tool(tool_name, tool_input)

                conversation_history.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": json.dumps(tool_result, default=str),
                        }
                    ],
                })
        else:
            text_blocks = [b for b in result.get("content", []) if b.get("type") == "text"]
            assistant_text = text_blocks[0]["text"] if text_blocks else result.get("content", "No response")
            if isinstance(assistant_text, list):
                assistant_text = str(assistant_text)
            conversation_history.append({"role": "assistant", "content": assistant_text})
            return assistant_text

    return "I wasn't able to complete that request — too many tool calls."


if __name__ == "__main__":
    print("🛒 Shopping Assistant (Claude 4.5 Haiku + MongoDB)")
    print("   Type your questions below. Type 'quit' to exit.\n")

    history = []
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break
        if not user_input:
            continue

        print()
        response = chat(user_input, history)
        print(f"Assistant: {response}\n")

    client.close()
