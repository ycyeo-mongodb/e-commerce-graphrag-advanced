"""
Solution: embed workshop.knowledge_base with Voyage AI ($set content_embedding).

Attendee lab: python scripts/TO-DO/11_embed_knowledge_base.py
"""

import os

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["knowledge_base"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

docs = list(coll.find({}))
texts = [f"{d.get('title', '')}\n{d.get('content', '')}".strip() for d in docs]
print(f"Loaded {len(docs)} knowledge_base documents")

result = vo.embed(texts, model="voyage-4-large", input_type="document")
embeddings = result.embeddings
print(f"Generated {len(embeddings)} embeddings of {len(embeddings[0])} dimensions")

for doc, embedding in zip(docs, embeddings):
    coll.update_one({"_id": doc["_id"]}, {"$set": {"content_embedding": embedding}})

print(f"Updated {coll.count_documents({'content_embedding': {'$exists': True}})} docs")
sample = coll.find_one({"title": {"$regex": "return", "$options": "i"}})
if sample and isinstance(sample.get("content_embedding"), list):
    print(f"  Returns article embedding length: {len(sample['content_embedding'])}")

client.close()
