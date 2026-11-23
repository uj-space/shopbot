export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000";

export interface Product {
  id: string;
  name: string;
  category: string;
  price_pkr: number;
  sizes: string;
  color: string;
  stock: number;
  description: string;
  upsell_with: string;
  created_at?: string;
}

export interface Order {
  id: string;
  user_id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  size: string;
  unit_price_pkr: number;
  shipping_pkr: number;
  total_pkr: number;
  delivery_address: string;
  status: "pending" | "confirmed" | "shipped" | "delivered" | "cancelled";
  created_at: string;
}

export interface UserMemory {
  mem_key: string;
  mem_value: string;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  user_id: string;
  thread_id: string;
  event_type: string;
  detail: string;
  tokens_in: number;
  tokens_out: number;
  created_at: string;
}

export interface Analytics {
  total_revenue_pkr: number;
  total_orders: number;
  active_orders: number;
  low_stock_products: number;
  total_products: number;
  total_tokens_in: number;
  total_tokens_out: number;
  safety_blocks: number;
}

export interface ChatToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface ChatResponse {
  reply: string;
  tool_calls: ChatToolCall[];
  tokens: { in: number; out: number };
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const errText = await res.text();
    try {
      const parsed = JSON.parse(errText) as { detail?: unknown };
      if (typeof parsed.detail === "string") {
        throw new Error(parsed.detail);
      }
    } catch (parseErr) {
      if (parseErr instanceof Error && parseErr.message && parseErr.message !== errText && !parseErr.message.includes("JSON")) {
        throw parseErr;
      }
    }
    throw new Error(errText || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: async () => {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    return res.ok ? await res.text() : "offline";
  },
  getProducts: (q = "", category = "") => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (category && category !== "All") params.set("category", category);
    const qs = params.toString();
    return fetchJson<Product[]>(`/api/products${qs ? `?${qs}` : ""}`);
  },
  upsertProduct: (product: Omit<Product, "created_at">) =>
    fetchJson<Product>("/api/products", {
      method: "POST",
      body: JSON.stringify(product),
    }),
  bulkProducts: (items: Array<Omit<Product, "created_at">>) =>
    fetchJson<{ inserted: number; products: Product[] }>("/api/products/bulk", {
      method: "POST",
      body: JSON.stringify(items),
    }),
  deleteProduct: (id: string) =>
    fetchJson<{ deleted: string }>(`/api/products/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  getOrders: (userId?: string) => {
    const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    return fetchJson<Order[]>(`/api/orders${qs}`);
  },
  updateOrderStatus: (orderId: string, status: Order["status"]) =>
    fetchJson<Order>(`/api/orders/${encodeURIComponent(orderId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  getAnalytics: () => fetchJson<Analytics>("/api/analytics"),
  getAuditLogs: (limit = 40) => fetchJson<AuditLog[]>(`/api/audit?limit=${limit}`),
  getMemories: (userId: string) =>
    fetchJson<UserMemory[]>(`/api/memories/${encodeURIComponent(userId)}`),
  clearMemories: (userId: string) =>
    fetchJson<{ cleared: number }>(`/api/memories/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    }),
  chat: (userId: string, threadId: string, message: string) =>
    fetchJson<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, thread_id: threadId, message }),
    }),
};
