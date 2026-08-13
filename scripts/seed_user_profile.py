#!/usr/bin/env python3
"""Seed demo shopper profile, sample orders, and memory-layer indexes."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient

load_dotenv()

DEMO_USER_ID = "demo_user"

DEMO_PROFILE = {
  "user_id": DEMO_USER_ID,
  "display_name": "Alex Chen",
  "email": "alex.chen@leafyshop.demo",
  "loyalty_tier": "gold",
  "member_since": datetime(2024, 3, 15, tzinfo=timezone.utc),
  "preferences": {
    "sizes": {"shoes": "US 10", "clothing": "M"},
    "favorite_brands": ["Nike", "Patagonia", "Sony"],
    "communication_style": "concise, friendly answers",
    "interests": [
      "running sneakers",
      "wireless headphones",
      "sustainable outdoor gear",
      "travel backpacks",
    ],
  },
  "recently_viewed": [
    {
      "product_name": "Heritage Slip-on Athletic Sneakers",
      "category": "Shoes",
      "brand": "Heritage",
      "viewed_at": datetime.now(timezone.utc) - timedelta(hours=6),
    },
    {
      "product_name": "Noise-Cancelling Wireless Headphones",
      "category": "Electronics",
      "brand": "Sony",
      "viewed_at": datetime.now(timezone.utc) - timedelta(days=1),
    },
  ],
  "updated_at": datetime.now(timezone.utc),
}

SAMPLE_ORDERS = [
  {
    "user_id": DEMO_USER_ID,
    "user_name": "Alex Chen",
    "items": [
      {
        "name": "Heritage Slip-on Athletic Sneakers",
        "price": 89.99,
        "category": "Shoes",
        "brand": "Heritage",
        "quantity": 1,
      }
    ],
    "total": 89.99,
    "item_count": 1,
    "search_mode_used": "hybrid",
    "created_at": datetime.now(timezone.utc) - timedelta(days=14),
  },
  {
    "user_id": DEMO_USER_ID,
    "user_name": "Alex Chen",
    "items": [
      {
        "name": "Trail Runner Pro Water Bottle",
        "price": 24.5,
        "category": "Sports & Outdoors",
        "brand": "Trail Runner",
        "quantity": 2,
      },
      {
        "name": "Organic Cotton Crew Tee",
        "price": 32.0,
        "category": "Clothing",
        "brand": "Patagonia",
        "quantity": 1,
      },
    ],
    "total": 81.0,
    "item_count": 3,
    "search_mode_used": "hybrid",
    "created_at": datetime.now(timezone.utc) - timedelta(days=45),
  },
]

LONG_TERM_MEMORIES = [
  {
    "user_id": DEMO_USER_ID,
    "session_id": "seed-session",
    "memory_scope": "long_term",
    "note": "Prefers concise answers and US shoe size 10",
    "created_at": datetime.now(timezone.utc) - timedelta(days=30),
  },
  {
    "user_id": DEMO_USER_ID,
    "session_id": "seed-session",
    "memory_scope": "long_term",
    "note": "Interested in sustainable brands and running gear",
    "created_at": datetime.now(timezone.utc) - timedelta(days=20),
  },
]


def main() -> None:
  uri = os.environ["MONGODB_URI"]
  client = MongoClient(uri)
  db = client["workshop"]

  profiles = db["user_profiles"]
  orders = db["orders"]
  memories = db["memories"]
  conversations = db["conversations"]

  profiles.delete_many({"user_id": DEMO_USER_ID})
  profiles.insert_one(DEMO_PROFILE)

  orders.delete_many({"user_id": DEMO_USER_ID})
  orders.insert_many(SAMPLE_ORDERS)

  memories.delete_many({"user_id": DEMO_USER_ID, "memory_scope": "long_term"})
  memories.insert_many(LONG_TERM_MEMORIES)

  profiles.create_index([("user_id", ASCENDING)], unique=True)
  orders.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
  memories.create_index([("user_id", ASCENDING), ("memory_scope", ASCENDING), ("created_at", ASCENDING)])
  memories.create_index([("session_id", ASCENDING), ("memory_scope", ASCENDING), ("created_at", ASCENDING)])
  conversations.create_index([("user_id", ASCENDING), ("session_id", ASCENDING), ("created_at", ASCENDING)])

  print(f"Seeded user_profiles.{DEMO_USER_ID} (Alex Chen)")
  print(f"Seeded {len(SAMPLE_ORDERS)} sample orders for {DEMO_USER_ID}")
  print(f"Seeded {len(LONG_TERM_MEMORIES)} long-term memories")
  print("Indexes ready on user_profiles, orders, memories, conversations")


if __name__ == "__main__":
  main()
