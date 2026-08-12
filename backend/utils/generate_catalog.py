#!/usr/bin/env python3
"""
Generate a 1000-item product catalog for workshop demos (stdlib only).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(42)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "public" / "data" / "products.json"

BRANDS = [
    "Northline Outfitters",
    "Velvet & Forge",
    "Aurora Thread Co.",
    "Summit Ridge Goods",
    "Blue Harbor Living",
    "Ironwood Supply",
    "Silverleaf Essentials",
    "Urban Meridian",
    "Coastal Drift",
    "Brightfield Labs",
    "Harbor & Hearth",
    "Pinecrest Workshop",
    "Emberline",
    "Clearwater Goods",
    "Trailhead Collective",
    "Nova Stitch",
    "Ridgepoint Gear",
    "Lumen Home",
    "Wilder & Co.",
    "Stonegate Outfitters",
    "Marlowe Street",
    "Cedar & Sky",
    "Pacific Threadworks",
    "Atlas Form",
    "Riverstone Supply",
    "Golden Hour Goods",
    "Nimbus Tech",
    "Fernwood Living",
    "Beacon Row",
    "Copperline",
    "Driftwood Studio",
    "Meadowbrook Basics",
    "Highline Athletic",
    "Olive & Oak",
    "Sterling Peak",
    "Crimson Tide Gear",
    "Lotus Lane",
    "Granite Trail",
    "Sable & Sage",
    "Horizon Works",
    "Twilight Row",
    "Birch Hollow",
    "Redwood Thread",
    "Cascade Supply",
    "Monarch Lane",
    "Fjord & Field",
    "Solstice Goods",
    "Inkwell Stationery",
    "Velour & Vine",
    "Quartzline Audio",
]

COLORS = [
    "midnight black",
    "charcoal",
    "navy",
    "slate gray",
    "ivory",
    "cream",
    "sand",
    "olive",
    "burgundy",
    "forest green",
    "cobalt",
    "terracotta",
    "rose quartz",
    "pearl white",
    "graphite",
    "camel",
    "wine red",
    "sky blue",
    "moss green",
    "espresso brown",
]

MATERIALS = [
    "full-grain leather",
    "organic cotton",
    "merino wool",
    "recycled polyester",
    "bamboo viscose",
    "stainless steel",
    "brushed aluminum",
    "tempered glass",
    "ceramic",
    "linen blend",
    "hemp canvas",
    "soft-touch silicone",
    "breathable mesh",
    "ripstop nylon",
    "cashmere blend",
]

FEATURES = [
    "moisture-wicking",
    "odor-resistant",
    "quick-dry",
    "UV protection",
    "reinforced stitching",
    "ergonomic shaping",
    "anti-slip",
    "temperature regulating",
    "scratch-resistant",
    "wireless convenience",
    "noise isolating",
    "adjustable fit",
    "packable design",
    "machine washable",
    "eco-certified materials",
]

USE_CASES = [
    "daily commuting",
    "weekend travel",
    "home offices",
    "outdoor workouts",
    "layering in changing weather",
    "long shifts on your feet",
    "minimalist packing",
    "gift-ready presentation",
    "sensitive skin routines",
    "high-traffic kitchens",
    "studio sessions",
    "rainy-day errands",
]

# Price ranges (min, max) per main category
PRICE_RANGES = {
    "Shoes": (29.99, 299.99),
    "Clothing": (14.99, 249.99),
    "Electronics": (9.99, 499.99),
    "Home & Kitchen": (8.99, 349.99),
    "Sports & Outdoors": (12.99, 279.99),
    "Beauty & Personal Care": (6.99, 189.99),
    "Books & Stationery": (4.99, 89.99),
    "Bags & Accessories": (11.99, 399.99),
}


def _split_counts(total: int, n: int) -> list[int]:
    base, rem = divmod(total, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def _build_name_templates(subcategory: str, style_words: list[str], cores: list[str], suffixes: list[str]) -> list[str]:
    """Cross-product style × core × suffix yields ~200+ patterns per category group."""
    out: list[str] = []
    for s in style_words:
        for c in cores:
            for x in suffixes:
                out.append(f"{s} {c} {x}".strip())
    return out


# Per-category: subcategory -> (count within cat handled externally), name template parts, tag hints
SHOES_SUB = [
    "sneakers",
    "running shoes",
    "boots",
    "sandals",
    "heels",
    "loafers",
    "hiking boots",
]
CLOTHING_SUB = [
    "t-shirts",
    "jeans",
    "dresses",
    "jackets",
    "hoodies",
    "sweaters",
    "shorts",
    "skirts",
]
ELECTRONICS_SUB = [
    "headphones",
    "speakers",
    "smartwatches",
    "phone cases",
    "chargers",
    "cables",
    "keyboards",
    "mice",
]
HOME_SUB = [
    "cookware",
    "storage",
    "decor",
    "lighting",
    "bedding",
    "towels",
    "kitchen gadgets",
]
SPORTS_SUB = [
    "yoga mats",
    "dumbbells",
    "water bottles",
    "backpacks",
    "camping gear",
    "cycling accessories",
]
BEAUTY_SUB = [
    "skincare",
    "haircare",
    "makeup",
    "fragrances",
    "grooming kits",
]
BOOKS_SUB = [
    "notebooks",
    "pens",
    "planners",
    "bookmarks",
    "desk organizers",
]
BAGS_SUB = [
    "handbags",
    "wallets",
    "belts",
    "sunglasses",
    "watches",
    "scarves",
]


def shoes_templates_for(sub: str) -> list[str]:
    pools = {
        "sneakers": (
            ["Retro", "Court", "Street", "Minimal", "Chunky", "Low-profile", "Heritage", "Performance", "Lifestyle", "Urban"],
            ["Canvas", "Knit", "Leather-trim", "Mesh-panel", "Suede-accent", "Slip-on", "Lace-up", "High-top", "Low-top", "Trainer"],
            ["Sneakers", "Trainers", "Athletic Sneakers", "Casual Sneakers", "Skate Sneakers"],
        ),
        "running shoes": (
            ["Carbon-plated", "Stability", "Neutral", "Trail-ready", "Road", "Lightweight", "Cushioned", "Responsive", "Daily trainer", "Tempo"],
            ["Foam-midsole", "Breathable-upper", "Grippy-outsole", "Reflective", "Wide-fit", "Narrow-fit", "Zero-drop", "Rockered", "Energy-return", "All-weather"],
            ["Running Shoes", "Runners", "Road Running Shoes", "Trail Running Shoes"],
        ),
        "boots": (
            ["Chelsea", "Combat", "Chukka", "Western-inspired", "Waterproof", "Insulated", "Slip-on", "Lace-up", "Ankle", "Mid-calf"],
            ["Leather", "Suede", "Waxed-canvas", "Shearling-lined", "Steel-toe", "Soft-toe", "Vibram-sole", "Stacked-heel", "Plain-toe", "Cap-toe"],
            ["Boots", "Ankle Boots", "Winter Boots", "Work Boots"],
        ),
        "sandals": (
            ["Sport", "Slide", "Strappy", "Gladiator-inspired", "Recovery", "Beach-ready", "Arch-support", "Minimalist", "Platform", "Fisherman"],
            ["EVA-foam", "Leather-strap", "Rubber-sole", "Cork-footbed", "Adjustable-buckle", "Quick-dry", "Contoured", "Wide-strap", "Toe-post", "Back-strap"],
            ["Sandals", "Slides", "Outdoor Sandals", "Casual Sandals"],
        ),
        "heels": (
            ["Block-heel", "Stiletto-inspired", "Kitten", "Platform", "Slingback", "Pump", "Ankle-strap", "Peep-toe", "Closed-toe", "Sculptural"],
            ["Patent", "Suede", "Satin-finish", "Leather-lined", "Cushioned-insole", "Stable-base", "Sculpted-heel", "Pointed-toe", "Round-toe", "Square-toe"],
            ["Heels", "Dress Heels", "Evening Heels", "Office Heels"],
        ),
        "loafers": (
            ["Penny", "Bit", "Tassel", "Driving", "Moccasin-style", "Classic", "Modern", "Soft-sole", "Structured", "Unlined"],
            ["Leather", "Suede", "Horsebit-detail", "Stitched-vamp", "Rubber-driver", "Stacked-heel", "Apron-toe", "Plain-vamp", "Woven", "Contrast-sole"],
            ["Loafers", "Casual Loafers", "Dress Loafers"],
        ),
        "hiking boots": (
            ["Mid-cut", "Low-cut", "Backpacking", "Day-hike", "Waterproof-breathable", "Insulated", "Aggressive-lug", "Light-hiker", "Approach-style", "Scramble-ready"],
            ["Gore-friendly", "Rubber-rand", "Toe-bumper", "Heel-lock", "Speed-lace", "Vibram-compatible", "Ankle-support", "Rock-plate", "Mesh-panel", "Nubuck"],
            ["Hiking Boots", "Trail Boots", "Backpacking Boots"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


def clothing_templates_for(sub: str) -> list[str]:
    pools = {
        "t-shirts": (
            ["Organic", "Heavyweight", "Vintage-wash", "Pocket", "Ribbed", "Oversized", "Slim-fit", "Cropped", "Longline", "Performance"],
            ["Crew-neck", "V-neck", "Henley", "Raglan", "Tee", "Base-layer", "Graphic-ready", "Essential", "Supima", "Slub-knit"],
            ["T-Shirt", "Tee", "Short-Sleeve Tee", "Essential Tee"],
        ),
        "jeans": (
            ["Straight", "Slim", "Relaxed", "Tapered", "Bootcut-inspired", "High-rise", "Mid-rise", "Low-stretch", "Rigid-denim", "Vintage"],
            ["Indigo", "Black-denim", "Light-wash", "Raw-denim", "Distressed-light", "Clean-finish", "Reinforced-pocket", "Selvedge-inspired", "Comfort-stretch", "Workwear"],
            ["Jeans", "Denim Jeans", "Five-Pocket Jeans"],
        ),
        "dresses": (
            ["Midi", "Maxi", "Mini", "Wrap-style", "Shirt-dress", "A-line", "Fit-and-flare", "Slip-inspired", "Knit", "Linen-blend"],
            ["Sleeveless", "Cap-sleeve", "Long-sleeve", "Belted", "Tiered", "Smocked", "Button-front", "Pleated", "Bias-cut", "Empire-waist"],
            ["Dress", "Day Dress", "Evening Dress", "Casual Dress"],
        ),
        "jackets": (
            ["Bomber", "Field", "Denim", "Quilted", "Utility", "Windbreaker", "Sherpa-lined", "Packable", "Overshirt", "Trucker"],
            ["Water-resistant", "Insulated", "Lightweight", "Stretch-panel", "Corduroy-collar", "Hidden-hood", "Multi-pocket", "Ripstop", "Wool-blend", "Technical-shell"],
            ["Jacket", "Outerwear Jacket", "Transitional Jacket"],
        ),
        "hoodies": (
            ["Pullover", "Zip-up", "Oversized", "Fitted", "Fleece-lined", "French-terry", "Heavyweight", "Athletic", "Streetwear", "Minimal"],
            ["Kangaroo-pocket", "Split-pocket", "Thumbhole-cuff", "Dropped-shoulder", "Rib-knit", "Garment-dyed", "Tonal-logo", "Three-panel-hood", "Tall-fit", "Petite-friendly"],
            ["Hoodie", "Hooded Sweatshirt", "Zip Hoodie"],
        ),
        "sweaters": (
            ["Cable-knit", "Ribbed", "Crewneck", "V-neck", "Cardigan-style", "Turtleneck", "Quarter-zip", "Shaker-stitch", "Donegal-inspired", "Featherweight"],
            ["Merino-blend", "Cotton-cashmere", "Alpaca-blend", "Wool-rich", "Machine-wash-friendly", "Breathable-open", "Structured-shoulder", "Relaxed-body", "Slim-sleeve", "Boxy"],
            ["Sweater", "Knit Sweater", "Pullover Sweater"],
        ),
        "shorts": (
            ["Chino", "Cargo-inspired", "Athletic", "Linen-blend", "Denim", "Bermuda-length", "5-inch", "7-inch", "9-inch", "Trail-ready"],
            ["Elastic-waist", "Belt-loop", "Hidden-zip-pocket", "Quick-dry", "Stretch-canvas", "Scalloped-hem", "Flat-front", "Pleated", "Lined", "Unlined"],
            ["Shorts", "Casual Shorts", "Athletic Shorts"],
        ),
        "skirts": (
            ["Pencil", "Pleated", "A-line", "Midi", "Maxi", "Denim", "Wrap", "Tiered", "Bias-cut", "Knit"],
            ["High-waist", "Side-zip", "Elastic-back", "Lined", "Unlined", "Slit-detail", "Button-front", "Patch-pocket", "Scuba-knit", "Linen-look"],
            ["Skirt", "Midi Skirt", "Casual Skirt"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


def electronics_templates_for(sub: str) -> list[str]:
    pools = {
        "headphones": (
            ["Over-ear", "On-ear", "Open-back-inspired", "Closed-back", "ANC", "Studio-monitor", "Travel", "Gaming-focused", "Call-ready", "Audiophile-friendly"],
            ["Bluetooth", "Wired-hybrid", "Dual-device", "Fold-flat", "Memory-foam", "Breathable-pad", "Hi-res codec", "Low-latency", "Ambient-aware", "Boom-mic"],
            ["Headphones", "Wireless Headphones", "Noise-Canceling Headphones"],
        ),
        "speakers": (
            ["Portable", "Bookshelf-style", "360-sound", "Waterproof", "Party", "Desktop", "Smart-assistant-ready", "Outdoor", "Compact", "Stereo-pairing"],
            ["Bass-radiator", "USB-C-charging", "AUX-in", "TWS-stereo", "Long-battery", "Fast-charge", "EQ-preset", "Rugged-shell", "Fabric-grille", "Aluminum-baffle"],
            ["Speaker", "Bluetooth Speaker", "Portable Speaker"],
        ),
        "smartwatches": (
            ["Fitness-first", "Outdoor-GPS", "AMOLED", "Always-on", "Slim-case", "Rugged", "Hybrid-display", "LTE-ready", "Budget-friendly", "Premium-build"],
            ["Heart-rate", "SpO2-ready", "Sleep-tracking", "Stress-insight", "5ATM", "Sapphire-inspired", "Swappable-band", "Voice-assistant", "Contactless-pay-ready", "Multi-sport"],
            ["Smartwatch", "Fitness Watch", "GPS Smartwatch"],
        ),
        "phone cases": (
            ["Slim", "Rugged", "Clear", "MagSafe-compatible", "Wallet-folio", "Grip-texture", "Biodegradable", "Shock-absorbing", "Camera-ring", "Raised-bezel"],
            ["TPU-bumper", "Polycarbonate-shell", "Leather-wrap", "Fabric-inlay", "Antimicrobial-coating", "Wireless-charge-friendly", "Lanyard-anchor", "Button-cover", "Port-dust-cover", "Corner-airbag"],
            ["Phone Case", "Protective Case", "Slim Case"],
        ),
        "chargers": (
            ["GaN", "Dual-port", "Triple-port", "Wireless-pad", "Wireless-stand", "Car", "Travel-fold", "Desktop-tower", "Magnetic", "Eco-packaging"],
            ["65W", "100W", "20W", "30W", "QC-compatible", "PD-compatible", "Smart-power", "Thermal-guard", "Compact-prong", "International-plug-ready"],
            ["Charger", "Wall Charger", "Fast Charger"],
        ),
        "cables": (
            ["Braided", "Silicone-soft", "Right-angle", "Short-travel", "Long-desk", "USB-C to USB-C", "USB-C to Lightning-ready", "HDMI", "DisplayPort", "Ethernet"],
            ["480Mbps", "10Gbps-ready", "240W-rated", "4K-ready", "8K-ready", "Gold-plated", "Strain-relief", "Velcro-tie", "Color-coded", "Reinforced-tip"],
            ["Cable", "Charging Cable", "Data Cable"],
        ),
        "keyboards": (
            ["Mechanical", "Low-profile", "Hot-swappable", "Wireless", "Wired", "Tenkeyless", "Full-size", "Compact-75%", "Split-ergo-inspired", "Silent-switch"],
            ["RGB-backlit", "White-backlit", "PBT-keycap", "Foam-dampened", "Mac-layout", "Windows-layout", "Multi-device", "USB-C-dongle", "Bluetooth-dual", "Programmable-layer"],
            ["Keyboard", "Mechanical Keyboard", "Wireless Keyboard"],
        ),
        "mice": (
            ["Ergonomic", "Ambidextrous", "Lightweight", "Ultra-light", "Office-quiet", "Gaming", "Trackball-inspired", "Vertical", "Compact", "Precision"],
            ["High-DPI", "Programmable-buttons", "Onboard-memory", "PTFE-feet", "USB-C-recharge", "Battery-AA", "Bluetooth-multi", "Textured-grip", "Scroll-toggle", "Low-latency"],
            ["Mouse", "Wireless Mouse", "Gaming Mouse"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


def home_templates_for(sub: str) -> list[str]:
    pools = {
        "cookware": (
            ["Nonstick", "Stainless", "Carbon-steel", "Enameled-cast", "Copper-core", "Hard-anodized", "Ceramic-coat", "Induction-ready", "Oven-safe", "Nesting"],
            ["Skillet", "Saucepan", "Sauté-pan", "Dutch-oven-style", "Griddle", "Wok", "Stockpot", "Grill-pan", "Casserole", "Egg-pan"],
            ["Cookware", "Pan Set", "Kitchen Pan"],
        ),
        "storage": (
            ["Airtight", "Stackable", "Glass", "Bamboo-lid", "Pantry", "Fridge", "Freezer-friendly", "Modular", "Label-ready", "Slim-profile"],
            ["Container-set", "Canister", "Cereal-dispenser", "Spice-rack", "Drawer-organizer", "Under-shelf", "Over-door", "Vacuum-seal", "Cereal-jar", "Dry-goods"],
            ["Storage Set", "Food Storage", "Pantry Containers"],
        ),
        "decor": (
            ["Minimal", "Bohemian", "Modern", "Scandi", "Industrial", "Coastal", "Art-deco-inspired", "Mid-century-nod", "Textured", "Handcrafted-look"],
            ["Wall-art", "Sculpture", "Vase", "Throw-pillow-cover", "Mirror", "Clock", "Candle-holder", "Tray", "Bookend", "Planter"],
            ["Home Decor", "Decor Accent", "Decor Piece"],
        ),
        "lighting": (
            ["LED", "Dimmable", "Smart-bulb-ready", "Warm-white", "Daylight", "Task", "Ambient", "Pendant-style", "Table-lamp", "Floor-lamp"],
            ["USB-powered", "Cordless", "Touch-control", "Remote", "Timer", "Color-tunable", "Metal-base", "Fabric-shade", "Glass-globe", "Articulating-arm"],
            ["Light", "Lamp", "LED Fixture"],
        ),
        "bedding": (
            ["Percale", "Sateen", "Linen-blend", "Jersey-knit", "Flannel", "Cooling", "Weighted-inspired", "Oeko-tex-minded", "Deep-pocket", "All-season"],
            ["Sheet-set", "Duvet-cover", "Quilt", "Comforter", "Pillowcase-pack", "Fitted-sheet", "Flat-sheet", "Sham-set", "Blanket", "Coverlet"],
            ["Bedding", "Sheet Set", "Bed Linens"],
        ),
        "towels": (
            ["Plush", "Quick-dry", "Turkish-inspired", "Waffle-weave", "Zero-twist", "Organic-cotton", "Microfiber", "Gym-size", "Hand-towel", "Beach-size"],
            ["600GSM-feel", "Lightweight", "Oversized", "Hanging-loop", "Colorfast", "Fade-resistant", "Set-of-two", "Set-of-four", "Bath-sheet", "Washcloth-pack"],
            ["Towel", "Towel Set", "Bath Towel"],
        ),
        "kitchen gadgets": (
            ["Multi-function", "Manual", "Electric", "Compact", "Pro-style", "Beginner-friendly", "Dishwasher-safe", "Heat-resistant", "Non-slip-base", "Measure-precise"],
            ["Peeler", "Grater", "Mandoline-inspired", "Immersion-blender", "Scale", "Thermometer", "Timer", "Can-opener", "Garlic-press", "Salad-spinner"],
            ["Kitchen Gadget", "Kitchen Tool", "Cooking Accessory"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


def sports_templates_for(sub: str) -> list[str]:
    pools = {
        "yoga mats": (
            ["Extra-thick", "Travel-fold", "Cork-top", "PU-surface", "Natural-rubber", "Alignment-line", "Hot-yoga", "Beginner", "Studio-grade", "Eco"],
            ["6mm", "5mm", "3mm", "Non-slip", "Closed-cell", "Open-cell", "Carry-strap", "Mat-bag-ready", "Odor-resistant", "Latex-free"],
            ["Yoga Mat", "Exercise Mat", "Studio Mat"],
        ),
        "dumbbells": (
            ["Hex", "Rubber-coated", "Neoprene", "Adjustable", "Fixed-weight", "Ergonomic-grip", "Studio-set", "Home-gym", "Compact", "Contoured"],
            ["5lb-pair", "10lb-pair", "15lb-pair", "20lb-pair", "25lb-pair", "2-20lb-range", "Stand-ready", "Knurled-handle", "Color-coded", "Square-head"],
            ["Dumbbells", "Hand Weights", "Hex Dumbbells"],
        ),
        "water bottles": (
            ["Insulated", "Straw-lid", "Chug-cap", "Wide-mouth", "Slim-bottle", "Gallon-inspired", "Fruit-infuser", "Filter-ready", "Bike-cage-fit", "Leak-proof"],
            ["Stainless", "Tritan", "Glass-sleeve", "Powder-coat", "Carry-loop", "Paracord-handle", "Measurement-markings", "Dishwasher-top-rack", "BPA-free", "Odor-resistant"],
            ["Water Bottle", "Insulated Bottle", "Sports Bottle"],
        ),
        "backpacks": (
            ["Daypack", "Travel", "Laptop", "Hiking", "Commuter", "Roll-top", "Clamshell", "Anti-theft", "Hydration-ready", "Minimal"],
            ["20L", "25L", "30L", "Ventilated-back", "Sternum-strap", "Laptop-sleeve", "Shoe-pocket", "RFID-pocket", "Recycled-fabric", "Weather-resistant"],
            ["Backpack", "Daypack", "Travel Backpack"],
        ),
        "camping gear": (
            ["Two-person", "Ultralight", "Three-season", "Four-season-ready", "Pop-up", "Backpacking", "Car-camping", "Family-size", "Solo", "Trekking-pole-compatible"],
            ["Tent", "Sleeping-bag", "Sleeping-pad", "Camp-stove", "Lantern", "Cooler-bag", "Tarp", "Hammock", "Camp-chair", "Mess-kit"],
            ["Camping Gear", "Camping Kit", "Outdoor Shelter"],
        ),
        "cycling accessories": (
            ["LED", "USB-recharge", "Helmet-mount", "Seat-post", "Handlebar", "CO2-ready", "Mini-pump", "Frame-bag", "Saddle-bag", "Phone-mount"],
            ["Bike-light-set", "Bell", "Bottle-cage", "Multi-tool", "Tire-lever", "Patch-kit", "Cycling-glove", "Arm-warmer", "Leg-warmer", "Clipless-pedal-cover"],
            ["Cycling Accessory", "Bike Accessory", "Ride Gear"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


def beauty_templates_for(sub: str) -> list[str]:
    pools = {
        "skincare": (
            ["Gentle", "Barrier-repair", "Brightening", "Hydrating", "Oil-control", "SPF-daily", "Retinol-alternative", "Niacinamide-rich", "Ceramide", "Fragrance-free"],
            ["Cleanser", "Serum", "Moisturizer", "Toner", "Essence", "Eye-cream", "Sunscreen", "Night-mask", "Spot-treatment", "Face-oil"],
            ["Skincare", "Face Care", "Daily Skincare"],
        ),
        "haircare": (
            ["Sulfate-free", "Color-safe", "Volumizing", "Smoothing", "Repairing", "Scalp-soothing", "Heat-protect", "Curl-defining", "Clarifying", "Dry-shampoo-style"],
            ["Shampoo", "Conditioner", "Mask", "Leave-in", "Oil-treatment", "Styling-cream", "Mousse", "Gel", "Finishing-spray", "Detangler"],
            ["Haircare", "Hair Treatment", "Hair Routine"],
        ),
        "makeup": (
            ["Longwear", "Buildable", "Matte", "Satin", "Dewy", "Transfer-resistant", "Vegan-friendly", "Cruelty-free-minded", "Shade-inclusive", "Beginner-friendly"],
            ["Foundation", "Concealer", "Blush", "Bronzer", "Highlighter", "Eyeshadow-palette", "Mascara", "Brow-pencil", "Lipstick", "Lip-gloss"],
            ["Makeup", "Cosmetic", "Beauty Makeup"],
        ),
        "fragrances": (
            ["Fresh", "Woody", "Floral", "Citrus", "Spicy", "Aquatic", "Gourmand-inspired", "Unisex", "Daytime", "Evening"],
            ["Eau-de-toilette-style", "Body-mist", "Roll-on", "Travel-atomizer", "Layering-set", "Hair-mist", "Solid-perfume-inspired", "Cologne-inspired", "Parfum-inspired", "Sample-set"],
            ["Fragrance", "Scent", "Perfume"],
        ),
        "grooming kits": (
            ["Travel", "TSA-friendly", "Beard-care", "Shave-kit", "Manicure", "Pedicure", "Brow-grooming", "Gifting", "Dopp-style", "Compact"],
            ["Trimmer", "Razor", "Brush", "Comb", "Scissors", "Nail-clipper", "Tweezer", "Mirror", "Cleansing-tool", "Organizer-case"],
            ["Grooming Kit", "Grooming Set", "Travel Grooming"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


def books_templates_for(sub: str) -> list[str]:
    pools = {
        "notebooks": (
            ["Dot-grid", "Lined", "Blank", "Hardcover", "Softcover", "Spiral", "Thread-bound", "Lay-flat", "Pocket-size", "A5"],
            ["160-page", "192-page", "240-page", "Archival-quality-paper", "Fountain-pen-friendly", "Recycled-paper", "Perforated", "Index-page", "Elastic-closure", "Ribbon-marker"],
            ["Notebook", "Journal", "Writing Notebook"],
        ),
        "pens": (
            ["Gel", "Ballpoint", "Rollerball", "Felt-tip", "Fineliner", "Retractable", "Click", "Twist", "Quick-dry", "Smudge-resistant"],
            ["0.5mm", "0.7mm", "1.0mm", "Blue-ink", "Black-ink", "Refillable", "Rubber-grip", "Metal-body", "Eco-barrel", "Clip-style"],
            ["Pen", "Writing Pen", "Gel Pen"],
        ),
        "planners": (
            ["Weekly", "Daily", "Monthly", "Academic-year", "Undated", "Goal-focused", "Minimal-layout", "Habit-tracker", "Budget-section", "Wellness-section"],
            ["Hardcover", "Spiral", "A5-size", "B6-size", "Sticker-friendly", "Pocket-folder", "Tabs", "Elastic-band", "Pen-loop", "Dated-year"],
            ["Planner", "Agenda", "Organizer Planner"],
        ),
        "bookmarks": (
            ["Magnetic", "Tassel", "Leather", "Metal", "Fabric", "Clip-style", "Elastic-band", "Page-marker-set", "Vintage-inspired", "Minimal"],
            ["Pack-of-three", "Pack-of-six", "Handmade-look", "Embossed", "Printed-quote", "Floral-motif", "Geometric", "Slim-profile", "Rounded-corner", "Gift-ready"],
            ["Bookmark", "Page Marker", "Reading Bookmark"],
        ),
        "desk organizers": (
            ["Drawer", "Desktop-caddy", "Monitor-stand", "Cable-management", "Pen-cup", "File-sorter", "Modular-tray", "Mesh", "Bamboo", "Acrylic"],
            ["Two-tier", "Three-tier", "Compartment-heavy", "Non-slip-feet", "Stackable", "Corner-fit", "Compact-footprint", "Laptop-riser", "Accessory-tray", "Memo-slot"],
            ["Desk Organizer", "Desktop Organizer", "Office Organizer"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


def bags_templates_for(sub: str) -> list[str]:
    pools = {
        "handbags": (
            ["Tote", "Crossbody", "Satchel", "Bucket", "Hobo", "Clutch-inspired", "Structured", "Slouchy", "Mini", "Work-tote"],
            ["Leather", "Vegan-leather", "Canvas", "Quilted", "Chain-strap", "Adjustable-strap", "Zip-top", "Magnetic-flap", "Interior-zip", "Feet-bottom"],
            ["Handbag", "Shoulder Bag", "Crossbody Bag"],
        ),
        "wallets": (
            ["Bifold", "Trifold", "Slim", "Zip-around", "Cardholder", "Passport-ready", "RFID-lined", "Money-clip-hybrid", "Coin-pocket", "ID-window"],
            ["Leather", "Saffiano-inspired", "Canvas", "Cork", "Recycled-material", "Contrast-stitch", "Minimal-silhouette", "Gift-boxed", "Embossed-logo-area", "Edge-painted"],
            ["Wallet", "Card Wallet", "Leather Wallet"],
        ),
        "belts": (
            ["Dress", "Casual", "Reversible", "Web", "Braided", "Western-inspired", "Stretch", "No-hole-ratchet", "Double-prong", "Skinny"],
            ["Leather", "Suede", "Canvas", "Nylon", "Matte-buckle", "Polished-buckle", "Nickel-free", "Cut-to-fit", "Plus-size-friendly", "Petite-friendly"],
            ["Belt", "Leather Belt", "Casual Belt"],
        ),
        "sunglasses": (
            ["Aviator-inspired", "Wayfarer-inspired", "Round", "Cat-eye", "Oversized", "Sport-wrap", "Polarized", "Gradient-lens", "Mirrored", "Blue-light-outdoor"],
            ["UV400", "Lightweight-frame", "Spring-hinge", "Adjustable-nose-pad", "TR90", "Metal-bridge", "Bio-acetate-inspired", "Carry-pouch", "Microfiber-cloth", "Unisex-fit"],
            ["Sunglasses", "Polarized Sunglasses", "UV Sunglasses"],
        ),
        "watches": (
            ["Chronograph-style", "Dress", "Field", "Diver-inspired", "Minimal", "Skeleton-inspired", "Solar-minded", "GMT-style", "Titanium-tone", "Two-tone"],
            ["Mesh-bracelet", "Leather-strap", "Silicone-strap", "Sapphire-coated-glass-inspired", "Luminous-hands", "Date-window", "Water-resistant", "Screw-down-crown-inspired", "Exhibition-caseback-inspired", "Quick-release-strap"],
            ["Watch", "Wristwatch", "Analog Watch"],
        ),
        "scarves": (
            ["Oversized", "Lightweight", "Wool-blend", "Cashmere-feel", "Silk-feel", "Plaid", "Houndstooth", "Solid", "Fringe", "Infinity-loop"],
            ["Winter-weight", "Spring-weight", "Travel-wrap", "Airplane-friendly", "Gift-boxed", "Handwash-friendly", "Anti-pill", "Breathable-weave", "Reversible-print", "Tassel-end"],
            ["Scarf", "Winter Scarf", "Fashion Scarf"],
        ),
    }
    a, b, c = pools[sub]
    return _build_name_templates(sub, a, b, c)


TEMPLATE_BUILDERS = {
    "Shoes": shoes_templates_for,
    "Clothing": clothing_templates_for,
    "Electronics": electronics_templates_for,
    "Home & Kitchen": home_templates_for,
    "Sports & Outdoors": sports_templates_for,
    "Beauty & Personal Care": beauty_templates_for,
    "Books & Stationery": books_templates_for,
    "Bags & Accessories": bags_templates_for,
}


def pick_name(category: str, subcategory: str, rng: random.Random) -> tuple[str, str | None]:
    """Return (display_name, edition_color) where edition_color matches a colorway when used."""
    builder = TEMPLATE_BUILDERS[category]
    templates = builder(subcategory)
    base = rng.choice(templates)
    if rng.random() < 0.45:
        if rng.random() < 0.68:
            flavor = rng.choice(COLORS)
            return f"{base} — {flavor.title()} edition", flavor
        flavor = rng.choice(MATERIALS).split()[0]
        return f"{base} — {flavor.title()} edition", None
    return base, None


def describe_shoes(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} pairs a {color} palette with {mat} accents for a polished everyday look. The upper is built for {use1}, while the outsole focuses on grip and confident footing. {feat.capitalize()} details help keep feet comfortable when you are on the move.",
        f"Designed for {use1}, this {sub} option balances support and flexibility without feeling bulky. The {color} finish reads modern in person, and the {mat} touches add subtle texture. Expect a ride that feels stable for {use2} while still looking sharp off the clock.",
        f"If you want footwear that can pivot between errands and light activity, {name} is a strong candidate. {feat.capitalize()} construction supports long wear, and the {mat} elements are chosen for durability. The {color} tone is versatile enough to anchor most outfits.",
        f"These {sub} emphasize comfort first: cushioning that does not feel mushy, plus a fit that stays secure during {use1}. {feat.capitalize()} materials help manage heat and friction, and the {color} styling keeps the silhouette clean. Great when you need one pair that can handle {use2}.",
        f"From the first step, you will notice how the {mat} components shape the feel—supportive where it matters, flexible where you bend. The {color} colorway photographs well and hides minor scuffs in real life. Ideal for {use1}, with enough polish for {use2} without looking overbuilt.",
    ]
    return rng.choice(variants)


def describe_clothing(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} is cut from {mat} that feels substantial but still breathes during {use1}. The {color} shade layers easily under jackets or stands alone. {feat.capitalize()} finishing reduces irritation at seams and helps the piece hold its shape wash after wash.",
        f"Whether you are dressing for {use1} or winding down afterward, this {sub} piece aims for an easy rhythm: soft hand-feel, clean lines, and a {color} tone that pairs with neutrals. {feat.capitalize()} details improve comfort during long wear, and the {mat} blend is chosen for everyday durability.",
        f"A wardrobe workhorse: {name} focuses on fit and fabric first. The {mat} construction drapes naturally, while {feat.lower()} properties make it practical for {use2}. The {color} finish reads elevated in natural light and stays versatile across seasons.",
        f"This is the kind of piece you reach for when you want comfort without looking casual-sloppy—especially in {sub}. {feat.capitalize()} touches—thoughtful stitching, stable hems—keep the silhouette intentional. The {color} palette and {mat} content make it easy to style for {use1}.",
        f"Built for real life, {name} handles {use1} and still looks composed for {use2}. The {mat} blend is soft against skin yet structured enough to hold a clean line. {feat.capitalize()} design choices help with temperature swings and everyday movement.",
    ]
    return rng.choice(variants)


def describe_electronics(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} is tuned for {use1}, with controls that feel intuitive after a day of use. {feat.capitalize()} engineering shows up in daily reliability—fewer dropouts, fewer surprises. The {color}-inspired finish and {mat} accents give it a refined desk or bag presence for {use2}.",
        f"If your setup spans {use1} and {use2}, this {sub} aims to be the uncomplicated part of the chain. Expect consistent performance, not gimmicks: stable connectivity, sensible ergonomics, and hardware details—like {mat} elements—meant to survive real commuting.",
        f"Designed around clarity and comfort, {name} makes long sessions easier. {feat.capitalize()} features reduce fatigue whether you are focused on work or winding down. The aesthetic leans modern with a {color} tone that blends into most spaces, while {mat} touches add a premium feel.",
        f"This {sub} prioritizes practical specs people actually notice: dependable battery behavior, straightforward pairing, and hardware that does not feel flimsy. {feat.capitalize()} choices support {use1}, and the overall design still looks intentional on a coffee table or nightstand during {use2}.",
        f"{name} fits best when you want performance without a steep learning curve. {feat.capitalize()} design supports everyday workflows—especially {use1}—and the finish reads clean in person thanks to {mat} surfaces and a {color}-leaning palette suited to {use2}.",
    ]
    return rng.choice(variants)


def describe_home(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} brings everyday function to {use1} without cluttering your counters or shelves. {feat.capitalize()} construction helps it survive real kitchens and busy households. The {mat} build feels solid in hand, and the {color} styling blends with a range of interiors.",
        f"Home upgrades should feel immediate: this {sub} item improves {use2} the first week you own it. {feat.capitalize()} details make routine tasks smoother, while the {mat} composition is chosen for longevity. The {color} tone photographs neutrally and looks cohesive in natural light.",
        f"Whether you are refreshing {use1} or tightening organization, {name} is built to earn its spot. Expect {feat.lower()} performance you will notice during cooking, cleaning, and hosting. {mat.capitalize()} elements add tactile quality, and the palette leans {color} for easy matching.",
        f"This piece is aimed at people who care about both aesthetics and upkeep. {feat.capitalize()} features reduce hassle during {use2}, and the silhouette stays timeless enough to move between rooms. The {mat} construction supports daily use, while {color} accents keep it feeling current.",
        f"{name} is a small change that reads bigger in person: better light, better flow, or better storage for {use1}. {feat.capitalize()} engineering shows up as fewer annoyances over time. The {color} finish pairs with wood tones and painted walls alike, and {mat} surfaces feel reassuringly sturdy.",
    ]
    return rng.choice(variants)


def describe_sports(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} is made for {use1}—stable where you need support, forgiving where you need mobility. {feat.capitalize()} materials hold up to repeated sessions and travel in a gym bag. The {mat} construction balances weight and durability, and the {color} look stays visible in mixed gear piles.",
        f"When you are training for {use2}, gear friction is the last thing you want. This {sub} option focuses on dependable basics: secure fit, sensible ergonomics, and {feat.lower()} touches that matter mid-workout. The {color} palette stays versatile, while {mat} components resist abrasion.",
        f"{name} targets athletes and weekend movers alike. It shines during {use1}, with details that reduce slipping, chafing, or awkward adjustments. {feat.capitalize()} design choices improve comfort over longer efforts, and the {mat} build feels purpose-built rather than decorative.",
        f"Outdoor-minded but still practical indoors, this {sub} supports {use2} without feeling over-specialized. {feat.capitalize()} features help in changing conditions, and the hardware does not feel flimsy when you are rushing between activities. The {color} accents and {mat} composition are chosen for real-world scuffs.",
        f"If you want equipment that respects your routine, {name} is structured around repeat use: easy to clean, easy to store, easy to trust. {feat.capitalize()} elements matter during {use1}, and the overall design still looks intentional when you are off the trail or out of the studio.",
    ]
    return rng.choice(variants)


def describe_beauty(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} is formulated for {use1}, with a texture that layers cleanly and finishes without a heavy film. {feat.capitalize()} ingredients support consistent results as your skin or hair changes with the season. The scent profile stays subtle—pleasant during {use2}, not overpowering in close spaces.",
        f"This {sub} product focuses on daily rituals: quick absorption, even application, and a {feat.lower()} approach that plays well with other steps in your routine. It is especially helpful when {use1} is your priority, but it still behaves politely under makeup or on busy mornings.",
        f"{name} balances efficacy and comfort—no sting-first philosophy, no chalky residue as a default. {feat.capitalize()} choices make it suitable for {use2}, while still targeting the concerns people mention in reviews: dryness, dullness, or uneven tone. Packaging is practical for counters and travel pouches alike.",
        f"Designed with sensitive routines in mind, this option emphasizes {feat.lower()} performance during {use1}. The formula feels intentional on skin or hair—spreadable, not grabby—and the experience stays pleasant through repeated use. Great if you want a dependable staple you can reach for without overthinking.",
        f"If you are building a streamlined shelf, {name} earns space by doing a few things very well. It supports {use2} with a finish that looks natural in daylight, and {feat.capitalize()} benefits show up as comfort over time rather than a single dramatic moment.",
    ]
    return rng.choice(variants)


def describe_books(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} is built for {use1}: pages that tolerate ink without feathering, and a layout that stays readable under café lighting. {feat.capitalize()} construction keeps spreads flat when you need them flat. The {color} cover treatment resists fingerprints, and {mat} accents give it a tactile, desk-worthy presence.",
        f"Stationery should disappear while you think—this {sub} item aims for that kind of quiet quality. {feat.capitalize()} details matter during {use2}, whether you are sketching, planning, or annotating. The paper tone pairs well with graphite and gel ink, and the exterior reads polished without being fragile.",
        f"{name} feels satisfying to use daily: balanced weight, smooth turning, and components that do not squeak or snag. It is especially handy for {use1}, with {feat.lower()} touches that reduce smudging and page curl. The {color} styling looks good in photos and on a shelf.",
        f"When deadlines stack, tools matter. This {sub} option supports {use2} with predictable performance—consistent lines, stable clips, and spacing that matches real handwriting. {feat.capitalize()} materials help it survive backpacks and briefcases, while {mat} finishes keep scuffs manageable.",
        f"{name} is a thoughtful upgrade from disposable supplies: better paper, better ergonomics, and details you notice after a week. {feat.capitalize()} design improves focus during {use1}, and the overall aesthetic—leaning {color}—fits modern desks without looking overly trendy.",
    ]
    return rng.choice(variants)


def describe_bags(sub: str, name: str, color: str, mat: str, feat: str, use1: str, use2: str, rng: random.Random) -> str:
    variants = [
        f"{name} is structured around real carrying: pockets where you expect them, hardware that does not dig in, and a silhouette that still looks intentional for {use1}. {feat.capitalize()} details improve comfort during {use2}. The {mat} body ages gracefully, and the {color} tone anchors outfits without shouting.",
        f"This {sub} piece is meant to simplify your day—less rummaging, fewer “where did I put it” moments. {feat.capitalize()} organization supports commuting and travel alike, while the materials lean {mat} for durability. The {color} palette reads sophisticated in person and pairs with both warm and cool wardrobes.",
        f"{name} balances polish and practicality: enough structure to protect essentials, enough softness to wear comfortably. {feat.capitalize()} stitching and hardware choices matter when you are moving quickly through {use1}. Expect a {color} finish that hides minor wear and {mat} surfaces that feel premium to the touch.",
        f"If you like accessories that work Monday through Sunday, this is a strong contender. It handles {use2} with sensible capacity and weight distribution, not gimmicky bulk. {feat.capitalize()} features keep cards, devices, and keys separated, while the {mat} construction and {color} styling stay versatile season to season.",
        f"{name} is designed for people who notice the small things: zipper glide, strap adjustability, and how a bag sits when you are walking fast. {feat.capitalize()} choices support {use1}, and the overall look stays refined enough for {use2}. The {mat} build and {color} tone make it easy to coordinate.",
    ]
    return rng.choice(variants)


DESCRIBERS = {
    "Shoes": describe_shoes,
    "Clothing": describe_clothing,
    "Electronics": describe_electronics,
    "Home & Kitchen": describe_home,
    "Sports & Outdoors": describe_sports,
    "Beauty & Personal Care": describe_beauty,
    "Books & Stationery": describe_books,
    "Bags & Accessories": describe_bags,
}


def make_tags(category: str, subcategory: str, name: str, color: str, rng: random.Random) -> list[str]:
    pool = [
        subcategory.replace("-", " "),
        category.split()[0].lower(),
        color,
        "everyday",
        "premium feel",
        "durable",
        "comfort",
        "modern design",
        "versatile",
        "gift idea",
        rng.choice(["bestseller vibe", "customer favorite", "editor's pick style", "new arrival energy"]),
        rng.choice(FEATURES).lower(),
        rng.choice(USE_CASES).split()[0],
    ]
    pool.extend(rng.sample(COLORS, k=4))
    pool.extend(rng.sample(MATERIALS, k=2))
    for word in name.replace("—", " ").split():
        w = word.strip(",.").lower()
        if len(w) > 3 and w not in ("edition", "style", "inspired"):
            pool.append(w)
    rng.shuffle(pool)
    n = rng.randint(3, 6)
    tags: list[str] = []
    for t in pool:
        if t not in tags:
            tags.append(t)
        if len(tags) >= n:
            break
    while len(tags) < n:
        tags.append(rng.choice(FEATURES).lower())
    return tags[:n]


def _feat_phrase(feat: str) -> str:
    return feat.replace("-", " ")


def make_product(
    pid: int,
    category: str,
    subcategory: str,
    rng: random.Random,
) -> dict:
    name, edition_color = pick_name(category, subcategory, rng)
    brand = rng.choice(BRANDS)
    color = edition_color if edition_color is not None else rng.choice(COLORS)
    mat = rng.choice(MATERIALS)
    feat = rng.choice(FEATURES)
    use1 = rng.choice(USE_CASES)
    use2 = rng.choice([u for u in USE_CASES if u != use1] or USE_CASES)
    description = DESCRIBERS[category](
        subcategory, name, color, mat, _feat_phrase(feat), use1, use2, rng
    )
    lo, hi = PRICE_RANGES[category]
    price = round(rng.uniform(lo, hi), 2)
    rating = round(rng.uniform(3.5, 5.0), 1)
    reviews_count = rng.randint(5, 5000)
    in_stock = rng.random() < 0.9
    tags = make_tags(category, subcategory, name, color, rng)
    return {
        "id": pid,
        "name": name,
        "category": category,
        "subcategory": subcategory,
        "description": description,
        "price": price,
        "brand": brand,
        "rating": rating,
        "reviews_count": reviews_count,
        "in_stock": in_stock,
        "tags": tags,
    }


def generate_catalog() -> list[dict]:
    spec: list[tuple[str, int, list[str]]] = [
        ("Shoes", 150, SHOES_SUB),
        ("Clothing", 200, CLOTHING_SUB),
        ("Electronics", 150, ELECTRONICS_SUB),
        ("Home & Kitchen", 120, HOME_SUB),
        ("Sports & Outdoors", 100, SPORTS_SUB),
        ("Beauty & Personal Care", 100, BEAUTY_SUB),
        ("Books & Stationery", 80, BOOKS_SUB),
        ("Bags & Accessories", 100, BAGS_SUB),
    ]
    rng = random.Random(42)
    products: list[dict] = []
    pid = 1
    for category, total, subs in spec:
        counts = _split_counts(total, len(subs))
        for sub, c in zip(subs, counts):
            for _ in range(c):
                products.append(make_product(pid, category, sub, rng))
                pid += 1
    assert len(products) == 1000
    assert pid == 1001
    return products


def print_summary(products: list[dict]) -> None:
    from collections import Counter

    by_cat = Counter(p["category"] for p in products)
    by_sub = Counter((p["category"], p["subcategory"]) for p in products)
    print("=== Catalog summary ===")
    print(f"Total products: {len(products)}")
    print("\nBy category:")
    for cat in [
        "Shoes",
        "Clothing",
        "Electronics",
        "Home & Kitchen",
        "Sports & Outdoors",
        "Beauty & Personal Care",
        "Books & Stationery",
        "Bags & Accessories",
    ]:
        print(f"  {cat}: {by_cat[cat]}")
    print("\nSample subcategory counts (category / subcategory):")
    for key in sorted(by_sub.keys(), key=lambda k: (k[0], k[1])):
        print(f"  {key[0]} / {key[1]}: {by_sub[key]}")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    products = generate_catalog()
    OUTPUT_PATH.write_text(json.dumps(products, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(products)} items)")
    print_summary(products)


if __name__ == "__main__":
    main()
