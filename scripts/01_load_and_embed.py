"""
Step 1: Load the product catalog and generate embeddings with Voyage AI.
Inserts all 1,000 products with embeddings into MongoDB Atlas.
"""

import json
import os
from pathlib import Path

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

# Load the product catalog
with open(Path(__file__).resolve().parent.parent / "backend" / "data" / "products.json") as f:
    products = json.load(f)

print(f"Loaded {len(products)} products")
print(f"Categories: {sorted(set(p['category'] for p in products))}")

# Generate embeddings in batches
descriptions = [p["description"] for p in products]
batch_size = 128
all_embeddings: list[list[float]] = []

for i in range(0, len(descriptions), batch_size):
    batch = descriptions[i : i + batch_size]
    result = vo.embed(batch, model="voyage-4-large", input_type="document")
    all_embeddings.extend(result.embeddings)
    print(f"  Embedded batch {i // batch_size + 1} ({len(all_embeddings)}/{len(descriptions)})")

# Attach embeddings to product documents
for product, embedding in zip(products, all_embeddings):
    product["description_embedding"] = embedding

print(f"Generated {len(all_embeddings)} embeddings of {len(all_embeddings[0])} dimensions")

# Insert into MongoDB
coll.delete_many({})
result = coll.insert_many(products)
print(f"Inserted {len(result.inserted_ids)} products into workshop.products")

# Verify
print(f"\nTotal products: {coll.count_documents({})}")
pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
for doc in coll.aggregate(pipeline):
    print(f"  {doc['_id']}: {doc['count']}")

client.close()
