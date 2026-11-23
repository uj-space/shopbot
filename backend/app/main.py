"""FastAPI application exposing grading endpoints + storefront & admin APIs."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from app import db
from app.config import CORS_ORIGINS
from app.graph import close_checkpointer, get_graph, invoke_chat

logger = logging.getLogger("shopbot.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        db.init_db()
        get_graph()
    except Exception:
        logger.exception("Warmup failed during startup")
    yield
    close_checkpointer()


app = FastAPI(title="ShopBot API — Khaas Studio", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    thread_id: str = Field(..., min_length=1)
    message: str = Field(...)

    @field_validator("user_id", "thread_id")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Must not be blank or whitespace only")
        return clean


class ProductIn(BaseModel):
    id: str | None = None
    name: str
    category: str = "Kurtas"
    price_pkr: int = Field(..., gt=0)
    sizes: str = "S, M, L"
    color: str = "Assorted"
    stock: int = Field(10, ge=0)
    description: str = ""
    upsell_with: str = ""


class OrderStatusPatch(BaseModel):
    status: str = Field(..., pattern="^(pending|confirmed|shipped|delivered|cancelled)$")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "ShopBot API — Khaas Studio"}


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.post("/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    try:
        db.init_db()
        return invoke_chat(user_id=req.user_id, thread_id=req.thread_id, message=req.message)
    except Exception as exc:
        logger.exception("Chat request failed for user=%s thread=%s", req.user_id, req.thread_id)
        try:
            db.log_audit(
                user_id=req.user_id,
                thread_id=req.thread_id,
                event_type="chat_error",
                detail=str(exc)[:300],
            )
        except Exception:
            pass
        return {
            "reply": "Sorry, ShopBot is temporarily unable to process that request. Please try again shortly.",
            "tool_calls": [],
            "tokens": {"in": 0, "out": 0},
        }


@app.get("/api/products")
def api_list_products(q: str = "", category: str = "", max_price: int | None = None) -> list[dict[str, Any]]:
    db.init_db()
    return db.list_products(query=q, category=category, max_price=max_price)


@app.post("/api/products")
def api_upsert_product(product: ProductIn) -> dict[str, Any]:
    db.init_db()
    return db.upsert_product(product.model_dump())


@app.post("/api/products/bulk")
def api_bulk_products(items: list[ProductIn]) -> dict[str, Any]:
    db.init_db()
    saved = [db.upsert_product(item.model_dump()) for item in items]
    return {"inserted": len(saved), "products": saved}


@app.delete("/api/products/{product_id}")
def api_delete_product(product_id: str) -> dict[str, Any]:
    db.init_db()
    if not db.delete_product(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return {"deleted": product_id}


@app.get("/api/orders")
def api_list_orders(user_id: str | None = None) -> list[dict[str, Any]]:
    db.init_db()
    return db.list_orders(user_id=user_id)


@app.patch("/api/orders/{order_id}/status")
def api_update_order_status(order_id: str, body: OrderStatusPatch) -> dict[str, Any]:
    db.init_db()
    try:
        updated = db.update_order_status(order_id=order_id, status=body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Order not found")
    return updated


@app.get("/api/analytics")
def api_analytics() -> dict[str, Any]:
    db.init_db()
    return db.get_analytics()


@app.get("/api/audit")
def api_audit_logs(limit: int = 40) -> list[dict[str, Any]]:
    db.init_db()
    return db.list_audit_logs(limit=limit)


@app.get("/api/memories/{user_id}")
def api_get_memories(user_id: str) -> list[dict[str, Any]]:
    db.init_db()
    return db.get_user_memories(user_id=user_id)


@app.delete("/api/memories/{user_id}")
def api_clear_memories(user_id: str) -> dict[str, Any]:
    db.init_db()
    count = db.clear_user_memories(user_id=user_id)
    return {"cleared": count}
