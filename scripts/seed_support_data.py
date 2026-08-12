#!/usr/bin/env python3
"""Seed fictional LeafyShop support knowledge and ensure indexes."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

KNOWLEDGE_DOCS = [
  {
    "title": "Vector search on LeafyShop catalog",
    "tags": ["vector search", "search", "compatibility"],
    "content": (
      "LeafyShop supports semantic product search powered by MongoDB Atlas Vector Search. "
      "Use hybrid mode when you need both keyword matching and meaning-based results. "
      "Vector search requires products to have description_embedding fields."
    ),
  },
  {
    "title": "Returns and refunds policy",
    "tags": ["returns", "policy", "support"],
    "content": (
      "LeafyShop accepts returns within 30 days for unused items in original packaging. "
      "Refunds are issued to the original payment method within 5–7 business days after inspection."
    ),
  },
  {
    "title": "Shipping and delivery",
    "tags": ["shipping", "delivery", "policy"],
    "content": (
      "Standard shipping is 3–5 business days. Express shipping is 1–2 business days. "
      "International orders may take 7–14 business days depending on customs."
    ),
  },
  {
    "title": "Product compatibility — footwear sizing",
    "tags": ["compatibility", "shoes", "sizing"],
    "content": (
      "LeafyShop footwear runs true to US sizing. Wide-fit variants are labeled in the product name. "
      "Compare skate and athletic sneakers by checking subcategory and tags for intended use."
    ),
  },
  {
    "title": "Warranty coverage",
    "tags": ["warranty", "policy", "support"],
    "content": (
      "Electronics and premium footwear include a 12-month manufacturer warranty against defects. "
      "Normal wear and tear, water damage, and unauthorized repairs are not covered."
    ),
  },
  {
    "title": "Account and order tracking",
    "tags": ["orders", "account", "support"],
    "content": (
      "Guests can track orders with order ID and email. Registered users see order history in My Orders. "
      "Checkout stores search_mode_used for analytics only."
    ),
  },
  {
    "title": "Atlas security for workshop deployments",
    "tags": ["security", "atlas", "mongodb"],
    "content": (
      "Use database users with least privilege. Restrict IP access lists after workshops. "
      "Never commit connection strings or API keys to source control."
    ),
  },
  {
    "title": "Backup and restore",
    "tags": ["backup", "atlas", "mongodb"],
    "content": (
      "MongoDB Atlas M0 clusters do not include continuous backup. "
      "For production LeafyShop catalogs, use M10+ with Cloud Backup enabled."
    ),
  },
]


def main() -> None:
  uri = os.environ["MONGODB_URI"]
  client = MongoClient(uri)
  db = client["workshop"]
  kb = db["knowledge_base"]
  memories = db["memories"]

  kb.delete_many({})
  now = datetime.now(timezone.utc)
  kb.insert_many([{**doc, "created_at": now} for doc in KNOWLEDGE_DOCS])

  memories.create_index([("session_id", ASCENDING), ("created_at", ASCENDING)])

  print(f"Seeded {len(KNOWLEDGE_DOCS)} knowledge_base documents into workshop.knowledge_base")
  print("memories collection ready (starts empty; agent writes per session)")


if __name__ == "__main__":
  main()
