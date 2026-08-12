"""
Step 7: Insert a bare product to trigger the Catalog Watcher.

This simulates a seller adding a product with minimal information.
The Catalog Watcher (06_catalog_watcher.py) will detect the insert
and dispatch it to the Enrichment Agent.

Usage:
    python 07_add_bare_product.py
    python 07_add_bare_product.py "Bamboo Cutting Board Set" 34.99
"""

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
collection = client["workshop"]["products"]

DEFAULT_PRODUCTS = [
    {"name": "Wireless Noise-Cancelling Headphones", "price": 89.99},
    {"name": "Bamboo Cutting Board Set", "price": 34.99},
    {"name": "Vintage Leather Messenger Bag", "price": 129.00},
    {"name": "USB-C Portable Monitor 15 inch", "price": 249.99},
    {"name": "Organic Green Tea Sampler Pack", "price": 18.50},
]

if len(sys.argv) >= 3:
    name = sys.argv[1]
    price = float(sys.argv[2])
else:
    import random
    product = random.choice(DEFAULT_PRODUCTS)
    name = product["name"]
    price = product["price"]

bare_product = {
    "name": name,
    "price": price,
    "status": "pending_enrichment",
}

result = collection.insert_one(bare_product)
print(f"✅ Inserted bare product: {result.inserted_id}")
print(f"   Name:   {name}")
print(f"   Price:  ${price}")
print(f"   Status: pending_enrichment")
print(f"\n   The Catalog Watcher should pick this up momentarily...")

client.close()
