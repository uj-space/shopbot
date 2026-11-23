"""Database-backed LangChain tools for ShopBot.

Every user-scoped tool reads `user_id` strictly from runtime context/config,
never from an LLM-supplied parameter, guaranteeing strict user isolation.
"""
from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app import db

_STOP_WORDS = {
    "for",
    "and",
    "the",
    "with",
    "under",
    "pkr",
    "outfits",
    "outfit",
    "items",
    "item",
    "clothes",
    "clothing",
    "show",
    "some",
    "any",
    "or",
}
_SIZE_ALIASES = {"SMALL": "S", "MEDIUM": "M", "LARGE": "L"}

_ctx_user_id: ContextVar[str] = ContextVar("shopbot_user_id", default="guest")
_ctx_turn_confirmed: ContextVar[bool] = ContextVar("shopbot_turn_confirmed", default=False)


def set_request_context(user_id: str, turn_confirmed: bool) -> tuple[Any, Any]:
    t1 = _ctx_user_id.set(user_id)
    t2 = _ctx_turn_confirmed.set(turn_confirmed)
    return t1, t2


def reset_request_context(tokens: tuple[Any, Any]) -> None:
    _ctx_user_id.reset(tokens[0])
    _ctx_turn_confirmed.reset(tokens[1])


def _get_user_id(config: RunnableConfig | None = None) -> str:
    if config and isinstance(config, dict):
        uid = config.get("configurable", {}).get("user_id")
        if uid:
            return str(uid)
    return _ctx_user_id.get()


def _is_turn_confirmed(config: RunnableConfig | None = None) -> bool:
    if config and isinstance(config, dict):
        cfg = config.get("configurable", {})
        if "turn_confirmed" in cfg:
            return bool(cfg["turn_confirmed"])
    return _ctx_turn_confirmed.get()


@tool
def search_catalog(query: str = "", category: str = "", max_price_pkr: int | None = None) -> str:
    """Search Khaas Studio's live product catalog by keyword, category, or max price in PKR."""
    items = db.list_products(query=query, category=category, max_price=max_price_pkr)
    if not items and query.strip():
        raw_tokens = re.findall(r"[a-z0-9-]+", query.lower())
        tokens: list[str] = []
        for raw in raw_tokens:
            if raw in _STOP_WORDS or len(raw) < 3:
                continue
            tok = raw[:-1] if len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss") else raw
            if tok not in tokens:
                tokens.append(tok)

        hits_by_id: dict[str, tuple[int, dict[str, Any]]] = {}
        for tok in tokens:
            for item in db.list_products(query=tok, category=category, max_price=max_price_pkr):
                pid = item["id"]
                prev_count = hits_by_id[pid][0] if pid in hits_by_id else 0
                hits_by_id[pid] = (prev_count + 1, item)

        if hits_by_id:
            sorted_hits = sorted(hits_by_id.values(), key=lambda pair: (-pair[0], pair[1]["id"]))
            items = [pair[1] for pair in sorted_hits]
    if not items:
        return "No matching products found in the catalog."
    lines = []
    for p in items[:10]:
        lines.append(
            f"[{p['id']}] {p['name']} ({p['category']}) — PKR {p['price_pkr']} | "
            f"Sizes: {p['sizes']} | Color: {p['color']} | Stock: {p['stock']} | {p['description']}"
        )
    return "\n".join(lines)


@tool
def get_upsell_recommendations(product_id_or_name: str) -> str:
    """Find complementary upsell items or accessories that pair well with a product."""
    prod = db.find_product(product_id_or_name)
    if not prod:
        return f"Product '{product_id_or_name}' was not found in the catalog."
    upsell_ids = [uid.strip() for uid in (prod.get("upsell_with") or "").split(",") if uid.strip()]
    recs = []
    for uid in upsell_ids:
        item = db.find_product(uid)
        if item and item["stock"] > 0:
            recs.append(f"[{item['id']}] {item['name']} — PKR {item['price_pkr']} ({item['color']}, Stock: {item['stock']})")
    if not recs:
        fallback = [p for p in db.list_products(category="Accessories") if p["id"] != prod["id"] and p["stock"] > 0]
        recs = [f"[{p['id']}] {p['name']} — PKR {p['price_pkr']} ({p['color']})" for p in fallback[:2]]
    return f"Recommended pairings for {prod['name']}:\n" + ("\n".join(recs) if recs else "No pairing items currently in stock.")


@tool
def save_user_preference(preference_key: str, preference_value: str, config: RunnableConfig) -> str:
    """Save a lasting customer shopping preference (e.g. size, style, color, city, budget) to long-term memory."""
    if db.SENSITIVE_MEMORY_RE.search(preference_key or "") or db.SENSITIVE_MEMORY_RE.search(preference_value or ""):
        return "Cannot save sensitive payment or credential details in long-term memory."
    user_id = _get_user_id(config)
    saved = db.upsert_user_memory(user_id=user_id, mem_key=preference_key, mem_value=preference_value)
    return f"Saved preference for your profile: {saved['mem_key']} = {saved['mem_value']}."


@tool
def calculate_order_total(product_id_or_name: str, quantity: int = 1) -> str:
    """Calculate exact subtotal, shipping fee, and grand total in PKR using live server-side prices."""
    if quantity <= 0:
        return "Quantity must be at least 1."
    prod = db.find_product(product_id_or_name)
    if not prod:
        return f"Product '{product_id_or_name}' not found."
    subtotal = int(prod["price_pkr"]) * quantity
    shipping = db.compute_shipping(subtotal)
    total = subtotal + shipping
    shipping_note = "FREE (orders >= PKR 6,000)" if shipping == 0 else f"PKR {shipping}"
    return (
        f"Price Breakdown for {quantity}x {prod['name']} [{prod['id']}]:\n"
        f"- Unit Price: PKR {prod['price_pkr']}\n"
        f"- Subtotal: PKR {subtotal}\n"
        f"- Delivery: {shipping_note}\n"
        f"- Grand Total: PKR {total}\n"
        f"- Available Stock: {prod['stock']}"
    )


@tool
def get_user_orders(config: RunnableConfig) -> str:
    """Retrieve orders belonging exclusively to the current active customer."""
    user_id = _get_user_id(config)
    orders = db.list_orders(user_id=user_id)
    if not orders:
        return "You have no orders yet."
    lines = []
    for o in orders[:10]:
        lines.append(
            f"{o['id']} | {o['quantity']}x {o['product_name']} (Size {o['size']}) | "
            f"Total: PKR {o['total_pkr']} | Status: {o['status']} | Deliver to: {o['delivery_address']}"
        )
    return "\n".join(lines)


@tool
def place_order(
    product_id_or_name: str,
    quantity: int = 1,
    size: str = "M",
    delivery_address: str = "",
    confirmed: bool = False,
    config: RunnableConfig = None,
) -> str:
    """Place a customer order. Must ONLY commit when the user explicitly confirmed in this turn."""
    user_id = _get_user_id(config)
    prod = db.find_product(product_id_or_name)
    if not prod:
        return f"Cannot place order: product '{product_id_or_name}' not found."
    if quantity <= 0:
        return "Quantity must be at least 1."
    if prod["stock"] < quantity:
        return f"Insufficient stock for {prod['name']} (available: {prod['stock']})."
    if not delivery_address.strip():
        return "Please ask the customer for a delivery address before placing the order."

    available_sizes = [s.strip() for s in (prod.get("sizes") or "").split(",") if s.strip()]
    if available_sizes == ["One Size"]:
        resolved_size = "One Size"
    else:
        norm_key = _SIZE_ALIASES.get(size.strip().upper(), size.strip().upper())
        size_lookup = {s.upper(): s for s in available_sizes}
        if norm_key not in size_lookup:
            return f"Size '{size}' is not available for {prod['name']}. Available sizes: {prod['sizes']}."
        resolved_size = size_lookup[norm_key]

    subtotal = int(prod["price_pkr"]) * quantity
    shipping = db.compute_shipping(subtotal)
    total = subtotal + shipping

    if not confirmed or not _is_turn_confirmed(config):
        return (
            f"CONFIRMATION_REQUIRED: Do not commit yet. Present this summary and ask the customer to reply 'yes' or 'confirm': "
            f"{quantity}x {prod['name']} (Size {resolved_size}) to '{delivery_address}' — "
            f"Subtotal PKR {subtotal} + Shipping PKR {shipping} = Total PKR {total}."
        )

    order = db.create_order(
        user_id=user_id,
        product_id=prod["id"],
        quantity=quantity,
        size=resolved_size,
        delivery_address=delivery_address.strip(),
    )
    return (
        f"ORDER_CONFIRMED: Order {order['id']} placed for {order['quantity']}x {order['product_name']} "
        f"(Size {order['size']}). Total: PKR {order['total_pkr']}. Status: {order['status']}."
    )


@tool
def cancel_order(order_id: str, confirmed: bool = False, config: RunnableConfig = None) -> str:
    """Cancel an order belonging to the current customer after explicit confirmation."""
    user_id = _get_user_id(config)
    mine = [o for o in db.list_orders(user_id=user_id) if o["id"].upper() == order_id.strip().upper()]
    if not mine:
        return f"Order '{order_id}' was not found under your account."
    order = mine[0]
    if order["status"] == "cancelled":
        return f"Order {order['id']} is already cancelled."
    if order["status"] in ("shipped", "delivered"):
        return f"Order {order['id']} is already {order['status']} and cannot be cancelled."

    if not confirmed or not _is_turn_confirmed(config):
        return (
            f"CONFIRMATION_REQUIRED: Ask the customer to confirm cancelling order {order['id']} "
            f"({order['quantity']}x {order['product_name']}, PKR {order['total_pkr']}) before cancelling."
        )

    updated = db.update_order_status(order["id"], "cancelled", required_user_id=user_id)
    if not updated:
        return f"Unable to cancel order '{order_id}'."
    return f"ORDER_CANCELLED: Order {updated['id']} has been cancelled and stock restored."


SALES_TOOLS = [search_catalog, get_upsell_recommendations, save_user_preference, calculate_order_total]
ORDER_TOOLS = [
    search_catalog,
    calculate_order_total,
    get_user_orders,
    place_order,
    cancel_order,
    save_user_preference,
]
