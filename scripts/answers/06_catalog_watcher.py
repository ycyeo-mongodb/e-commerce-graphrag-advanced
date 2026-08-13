"""
Step 6: Catalog Watcher Agent — watches for new product inserts via Change Streams.

When a seller adds a bare product (name + price), this agent detects it
instantly and dispatches it to the enrichment pipeline.

Usage:
    python 06_catalog_watcher.py

Keep this running in a separate terminal while inserting products.
"""

import os
import json
import signal
import sys
from datetime import datetime, timezone

import requests
import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
db = client["workshop"]
collection = db["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

BEDROCK_API_URL = os.environ.get("BEDROCK_API_URL", "")


def generate_product_details(name: str, price: float) -> dict:
    """Call Claude 4.5 Haiku to generate structured product details."""
    prompt = (
        "You are a product catalog AI. Given a product name and price, "
        "generate detailed e-commerce listing information.\n\n"
        f"Product Name: {name}\n"
        f"Price: ${price}\n\n"
        "Respond with ONLY valid JSON in this exact format:\n"
        '{\n'
        '  "description": "A detailed 2-3 sentence product description",\n'
        '  "category": "TopCategory > SubCategory",\n'
        '  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],\n'
        '  "brand": "BrandName or Generic"\n'
        '}'
    )

    response = requests.post(
        BEDROCK_API_URL,
        json={
            "action": "answer",
            "question": prompt,
            "context": "",
            "max_tokens": 500,
            "temperature": 0.3,
        },
        timeout=30,
    )
    result = response.json()
    answer = result.get("answer", "")

    start = answer.find("{")
    end = answer.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(answer[start:end])
    return json.loads(answer)


def generate_embedding(text: str) -> list[float]:
    """Generate a 1024d embedding using Voyage AI."""
    result = vo.embed([text], model="voyage-4-large", input_type="document")
    return result.embeddings[0]


def enrich_product(doc_id, name: str, price: float):
    """Full enrichment pipeline: Claude → Voyage AI → MongoDB update."""
    print(f"   → Dispatching to Enrichment Agent...")

    details = generate_product_details(name, price)
    print(f"   - Description: {len(details.get('description', ''))} chars generated")
    print(f"   - Category: {details.get('category', 'Unknown')}")
    print(f"   - Tags: {details.get('tags', [])}")

    embedding = generate_embedding(details["description"])
    print(f"   - Embedding: {len(embedding)} dimensions generated")

    collection.update_one(
        {"_id": doc_id},
        {
            "$set": {
                "description": details["description"],
                "category": details.get("category", "Uncategorized"),
                "tags": details.get("tags", []),
                "brand": details.get("brand", "Generic"),
                "description_embedding": embedding,
                "status": "active",
                "enriched_by": "claude-4.5-haiku",
                "enriched_at": datetime.now(timezone.utc),
            }
        },
    )
    print(f"   - Status: active")
    print(f"✅ Enrichment complete!\n")


def handle_exit(signum, frame):
    print("\n\n👋 Catalog Watcher stopped.")
    client.close()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_exit)

pipeline = [
    {
        "$match": {
            "operationType": "insert",
            "fullDocument.status": "pending_enrichment",
        }
    }
]

print("🔄 Catalog Watcher Agent started")
print("   Watching 'workshop.products' for new inserts...")
if not BEDROCK_API_URL:
    print("   ⚠ BEDROCK_API_URL not set — enrichment will fail")
print("   (Press Ctrl+C to stop)\n")

with collection.watch(pipeline) as stream:
    for change in stream:
        doc = change["fullDocument"]
        print(f"📦 New product detected: {doc['name']}")
        print(f"   Status: {doc['status']}")

        try:
            enrich_product(doc["_id"], doc["name"], doc.get("price", 0))
        except Exception as e:
            print(f"   ❌ Enrichment failed: {e}\n")
