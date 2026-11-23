"""Persistent storage layer supporting PostgreSQL (Supabase/Neon) with SQLite local fallback."""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import DATABASE_URL, FLAT_SHIPPING_PKR, FREE_SHIPPING_THRESHOLD_PKR, SQLITE_PATH

SENSITIVE_MEMORY_RE = re.compile(
    r"\b(?:\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7}|\d{5}-\d{7}-\d|password|passcode|cvv|pin|cnic|credit[\s_]?card|debit[\s_]?card|card[\s_]?number)\b",
    re.I,
)

_pg_db_pool = None
_pg_pool_lock = threading.Lock()


def is_postgres() -> bool:
    url = os.getenv("DATABASE_URL", DATABASE_URL).strip()
    return url.startswith("postgres://") or url.startswith("postgresql://")


def _db_url() -> str:
    return os.getenv("DATABASE_URL", DATABASE_URL).strip()


def _sqlite_path() -> str:
    return os.getenv("SQLITE_PATH", SQLITE_PATH).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _adapt_sql(sql: str) -> str:
    if is_postgres():
        return sql.replace("?", "%s")
    return sql


def _get_pg_pool():
    global _pg_db_pool
    if _pg_db_pool is not None:
        return _pg_db_pool
    with _pg_pool_lock:
        if _pg_db_pool is not None:
            return _pg_db_pool
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        _pg_db_pool = ConnectionPool(
            conninfo=_db_url(),
            min_size=1,
            max_size=10,
            max_idle=60,
            check=ConnectionPool.check_connection,
            kwargs={"row_factory": dict_row, "autocommit": False, "prepare_threshold": 0},
        )
    return _pg_db_pool


@contextmanager
def get_conn():
    if is_postgres():
        with _get_pg_pool().connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    else:
        conn = sqlite3.connect(_sqlite_path(), check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


SEED_PRODUCTS = [
    {
        "id": "KS-101",
        "name": "Emerald Lawn Kurta",
        "category": "Kurtas",
        "price_pkr": 3850,
        "sizes": "S, M, L, XL",
        "color": "Emerald Green",
        "stock": 24,
        "description": "Breathable 3-piece summer Swiss lawn kurta with minimal neckline embroidery.",
        "upsell_with": "KS-201,KS-301",
    },
    {
        "id": "KS-102",
        "name": "Ivory Cotton Kurta",
        "category": "Kurtas",
        "price_pkr": 3200,
        "sizes": "S, M, L, XL",
        "color": "Ivory",
        "stock": 18,
        "description": "Classic handloom cotton kurta tailored for warm Islamabad and Lahore afternoons.",
        "upsell_with": "KS-202,KS-302",
    },
    {
        "id": "KS-103",
        "name": "Blush Pastel Chikankari Co-ord",
        "category": "Co-ords",
        "price_pkr": 4800,
        "sizes": "S, M, L",
        "color": "Blush Pastel",
        "stock": 15,
        "description": "Two-piece pastel pink chikankari shirt and relaxed trouser set.",
        "upsell_with": "KS-201,KS-301",
    },
    {
        "id": "KS-104",
        "name": "Charcoal Linen Shirt",
        "category": "Menswear",
        "price_pkr": 3950,
        "sizes": "M, L, XL",
        "color": "Charcoal",
        "stock": 20,
        "description": "Tailored breathable linen Mandarin-collar shirt for smart-casual wear.",
        "upsell_with": "KS-302",
    },
    {
        "id": "KS-201",
        "name": "Silk Block-Print Dupatta",
        "category": "Dupattas & Shawls",
        "price_pkr": 1850,
        "sizes": "One Size",
        "color": "Sage & Gold",
        "stock": 30,
        "description": "Lightweight pure silk dupatta with artisan block-printed border.",
        "upsell_with": "KS-101,KS-103",
    },
    {
        "id": "KS-202",
        "name": "Velvet Evening Shawl",
        "category": "Dupattas & Shawls",
        "price_pkr": 6800,
        "sizes": "One Size",
        "color": "Midnight Plum",
        "stock": 9,
        "description": "Plush winter micro-velvet shawl finished with antique tilla edging.",
        "upsell_with": "KS-102,KS-301",
    },
    {
        "id": "KS-301",
        "name": "Handcrafted Gold Khussa",
        "category": "Accessories",
        "price_pkr": 2650,
        "sizes": "37, 38, 39, 40, 41",
        "color": "Antique Gold",
        "stock": 14,
        "description": "Cushioned leather-sole khussa embroidered in Multan.",
        "upsell_with": "KS-101,KS-103",
    },
    {
        "id": "KS-302",
        "name": "Tan Leather Everyday Tote",
        "category": "Accessories",
        "price_pkr": 5400,
        "sizes": "One Size",
        "color": "Warm Tan",
        "stock": 11,
        "description": "Full-grain camel leather tote fitting a 14-inch laptop and daily essentials.",
        "upsell_with": "KS-102,KS-104",
    },
]


_db_initialized: bool = False


def init_db(force: bool = False) -> None:
    """Create tables if missing and seed initial store catalog if empty."""
    global _db_initialized
    if _db_initialized and not force:
        return
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price_pkr INTEGER NOT NULL,
                sizes TEXT NOT NULL,
                color TEXT NOT NULL,
                stock INTEGER NOT NULL,
                description TEXT NOT NULL,
                upsell_with TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                size TEXT NOT NULL,
                unit_price_pkr INTEGER NOT NULL,
                shipping_pkr INTEGER NOT NULL,
                total_pkr INTEGER NOT NULL,
                delivery_address TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                mem_key TEXT NOT NULL,
                mem_value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (user_id, mem_key)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL,
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute("SELECT COUNT(*) AS cnt FROM products")
        row = cur.fetchone()
        count = dict(row)["cnt"] if row else 0
        if count == 0:
            now = _utc_now()
            for p in SEED_PRODUCTS:
                cur.execute(
                    _adapt_sql(
                        """
                        INSERT INTO products (id, name, category, price_pkr, sizes, color, stock, description, upsell_with, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                    ),
                    (
                        p["id"],
                        p["name"],
                        p["category"],
                        p["price_pkr"],
                        p["sizes"],
                        p["color"],
                        p["stock"],
                        p["description"],
                        p["upsell_with"],
                        now,
                    ),
                )
    _db_initialized = True


def list_products(query: str = "", category: str = "", max_price: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        clauses = ["1=1"]
        params: list[Any] = []
        if query.strip():
            like = f"%{query.strip().lower()}%"
            clauses.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(color) LIKE ? OR LOWER(category) LIKE ?)")
            params.extend([like, like, like, like])
        if category.strip() and category.strip().lower() != "all":
            clauses.append("LOWER(category) = ?")
            params.append(category.strip().lower())
        if max_price is not None:
            clauses.append("price_pkr <= ?")
            params.append(int(max_price))
        sql = f"SELECT * FROM products WHERE {' AND '.join(clauses)} ORDER BY id ASC"
        cur.execute(_adapt_sql(sql), tuple(params))
        return _rows_to_dicts(cur.fetchall())


def find_product(product_id_or_name: str) -> dict[str, Any] | None:
    target = product_id_or_name.strip().lower()
    if not target:
        return None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            _adapt_sql("SELECT * FROM products WHERE LOWER(id) = ? OR LOWER(name) = ? LIMIT 1"),
            (target, target),
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        cur.execute(
            _adapt_sql("SELECT * FROM products WHERE LOWER(name) LIKE ? ORDER BY id ASC LIMIT 1"),
            (f"%{target}%",),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

        singular = target[:-1] if len(target) > 3 and target.endswith("s") and not target.endswith("ss") else target
        if singular != target:
            cur.execute(
                _adapt_sql("SELECT * FROM products WHERE LOWER(name) LIKE ? ORDER BY id ASC LIMIT 1"),
                (f"%{singular}%",),
            )
            row = cur.fetchone()
            if row:
                return dict(row)

        tokens = [
            t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t
            for t in re.findall(r"[a-z0-9]+", target)
            if len(t) >= 2
        ]
        if not tokens:
            return None
        cur.execute("SELECT * FROM products ORDER BY id ASC")
        all_products = _rows_to_dicts(cur.fetchall())
        min_hits = 2 if len(tokens) >= 2 else 1
        best_prod = None
        best_score = 0
        for prod in all_products:
            name_lower = prod["name"].lower()
            score = sum(1 for tok in tokens if tok in name_lower)
            if score >= min_hits and score > best_score:
                best_score = score
                best_prod = prod
        return best_prod


def upsert_product(data: dict[str, Any]) -> dict[str, Any]:
    pid = (data.get("id") or f"KS-{uuid4().hex[:4].upper()}").strip()
    now = _utc_now()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            _adapt_sql(
                """
                INSERT INTO products (id, name, category, price_pkr, sizes, color, stock, description, upsell_with, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    price_pkr = EXCLUDED.price_pkr,
                    sizes = EXCLUDED.sizes,
                    color = EXCLUDED.color,
                    stock = EXCLUDED.stock,
                    description = EXCLUDED.description,
                    upsell_with = EXCLUDED.upsell_with
                """
            ),
            (
                pid,
                data["name"],
                data.get("category", "General"),
                int(data["price_pkr"]),
                data.get("sizes", "S, M, L"),
                data.get("color", "Assorted"),
                int(data.get("stock", 10)),
                data.get("description", ""),
                data.get("upsell_with", ""),
                now,
            ),
        )
        cur.execute(_adapt_sql("SELECT * FROM products WHERE id = ?"), (pid,))
        return dict(cur.fetchone())


def delete_product(product_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_adapt_sql("DELETE FROM products WHERE id = ?"), (product_id,))
        return cur.rowcount > 0


def compute_shipping(subtotal_pkr: int) -> int:
    return 0 if subtotal_pkr >= FREE_SHIPPING_THRESHOLD_PKR else FLAT_SHIPPING_PKR


def create_order(
    user_id: str,
    product_id: str,
    quantity: int,
    size: str,
    delivery_address: str,
) -> dict[str, Any]:
    if quantity <= 0:
        raise ValueError("Quantity must be at least 1.")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_adapt_sql("SELECT * FROM products WHERE id = ?"), (product_id,))
        prod_row = cur.fetchone()
        if not prod_row:
            raise ValueError(f"Product {product_id} not found.")
        prod = dict(prod_row)

        cur.execute(
            _adapt_sql("UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?"),
            (quantity, product_id, quantity),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Insufficient stock for {prod['name']} (available: {prod['stock']}).")

        subtotal = int(prod["price_pkr"]) * quantity
        shipping = compute_shipping(subtotal)
        total = subtotal + shipping
        order_id = f"ORD-{uuid4().hex[:6].upper()}"
        now = _utc_now()
        cur.execute(
            _adapt_sql(
                """
                INSERT INTO orders (
                    id, user_id, product_id, product_name, quantity, size,
                    unit_price_pkr, shipping_pkr, total_pkr, delivery_address, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
            ),
            (
                order_id,
                user_id,
                prod["id"],
                prod["name"],
                quantity,
                size,
                int(prod["price_pkr"]),
                shipping,
                total,
                delivery_address,
                "confirmed",
                now,
            ),
        )
        cur.execute(_adapt_sql("SELECT * FROM orders WHERE id = ?"), (order_id,))
        return dict(cur.fetchone())


def list_orders(user_id: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute(
                _adapt_sql("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC"),
                (user_id,),
            )
        else:
            cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
        return _rows_to_dicts(cur.fetchall())


def update_order_status(order_id: str, status: str, required_user_id: str | None = None) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.cursor()
        if required_user_id is not None:
            cur.execute(
                _adapt_sql("SELECT * FROM orders WHERE id = ? AND user_id = ?"),
                (order_id, required_user_id),
            )
        else:
            cur.execute(_adapt_sql("SELECT * FROM orders WHERE id = ?"), (order_id,))
        existing = cur.fetchone()
        if not existing:
            return None
        existing_dict = dict(existing)

        prev_status = existing_dict["status"]
        if status == "cancelled" and prev_status != "cancelled":
            cur.execute(
                _adapt_sql("UPDATE products SET stock = stock + ? WHERE id = ?"),
                (existing_dict["quantity"], existing_dict["product_id"]),
            )
        elif prev_status == "cancelled" and status != "cancelled":
            cur.execute(
                _adapt_sql("UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?"),
                (existing_dict["quantity"], existing_dict["product_id"], existing_dict["quantity"]),
            )
            if cur.rowcount == 0:
                raise ValueError(
                    f"Insufficient stock to reactivate order {order_id} ({existing_dict['quantity']}x {existing_dict['product_name']})."
                )
        cur.execute(
            _adapt_sql("UPDATE orders SET status = ? WHERE id = ?"),
            (status, order_id),
        )
        cur.execute(_adapt_sql("SELECT * FROM orders WHERE id = ?"), (order_id,))
        return dict(cur.fetchone())


def upsert_user_memory(user_id: str, mem_key: str, mem_value: str) -> dict[str, Any]:
    if SENSITIVE_MEMORY_RE.search(mem_key or "") or SENSITIVE_MEMORY_RE.search(mem_value or ""):
        raise ValueError("Sensitive credentials or payment details cannot be stored in long-term memory.")
    clean_key = mem_key.strip().lower()[:40]
    clean_val = mem_value.strip()[:240]
    now = _utc_now()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            _adapt_sql(
                """
                INSERT INTO user_memories (id, user_id, mem_key, mem_value, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (user_id, mem_key) DO UPDATE SET
                    mem_value = EXCLUDED.mem_value,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            (f"MEM-{uuid4().hex[:8]}", user_id, clean_key, clean_val, now),
        )
        cur.execute(
            _adapt_sql("SELECT * FROM user_memories WHERE user_id = ? AND mem_key = ?"),
            (user_id, clean_key),
        )
        return dict(cur.fetchone())


def get_user_memories(user_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            _adapt_sql("SELECT mem_key, mem_value, updated_at FROM user_memories WHERE user_id = ? ORDER BY updated_at DESC"),
            (user_id,),
        )
        return _rows_to_dicts(cur.fetchall())


def clear_user_memories(user_id: str) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_adapt_sql("DELETE FROM user_memories WHERE user_id = ?"), (user_id,))
        return cur.rowcount


def log_audit(
    user_id: str,
    thread_id: str,
    event_type: str,
    detail: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            _adapt_sql(
                """
                INSERT INTO audit_logs (id, user_id, thread_id, event_type, detail, tokens_in, tokens_out, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
            ),
            (f"AUD-{uuid4().hex[:8]}", user_id, thread_id, event_type, detail[:500], int(tokens_in), int(tokens_out), _utc_now()),
        )


def list_audit_logs(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_adapt_sql("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?"), (int(limit),))
        return _rows_to_dicts(cur.fetchall())


def get_analytics() -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, total_pkr FROM orders")
        orders = _rows_to_dicts(cur.fetchall())
        active_orders = [o for o in orders if o["status"] != "cancelled"]
        revenue_pkr = sum(int(o["total_pkr"]) for o in active_orders)

        cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE stock <= 10")
        low_stock = dict(cur.fetchone())["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM products")
        total_products = dict(cur.fetchone())["cnt"]

        cur.execute("SELECT COALESCE(SUM(tokens_in), 0) AS tin, COALESCE(SUM(tokens_out), 0) AS tout FROM audit_logs")
        tok = dict(cur.fetchone())

        cur.execute("SELECT COUNT(*) AS cnt FROM audit_logs WHERE event_type = 'safety_blocked'")
        blocked_count = dict(cur.fetchone())["cnt"]

        return {
            "total_revenue_pkr": revenue_pkr,
            "total_orders": len(orders),
            "active_orders": len(active_orders),
            "low_stock_products": low_stock,
            "total_products": total_products,
            "total_tokens_in": int(tok["tin"] or 0),
            "total_tokens_out": int(tok["tout"] or 0),
            "safety_blocks": blocked_count,
        }
