"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  Coins,
  PackageCheck,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShoppingBag,
  Trash2,
  Upload,
} from "lucide-react";
import { Analytics, api, AuditLog, Order, Product } from "@/lib/api";

const ORDER_STATUSES: Order["status"][] = [
  "pending",
  "confirmed",
  "shipped",
  "delivered",
  "cancelled",
];

function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      fields.push(cur.trim());
      cur = "";
    } else {
      cur += ch;
    }
  }
  fields.push(cur.trim());
  return fields;
}

export default function AdminDashboardPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [banner, setBanner] = useState("");

  // Add Product form state
  const [name, setName] = useState("");
  const [category, setCategory] = useState("Kurtas");
  const [pricePkr, setPricePkr] = useState("4200");
  const [sizes, setSizes] = useState("S, M, L, XL");
  const [color, setColor] = useState("Teal");
  const [stock, setStock] = useState("15");
  const [upsellWith, setUpsellWith] = useState("KS-201");
  const [description, setDescription] = useState("");

  // Bulk JSON/CSV upload state
  const [bulkText, setBulkText] = useState("");

  const loadAdminData = useCallback(async () => {
    setLoading(true);
    try {
      const [stats, allOrders, allProducts, logs] = await Promise.all([
        api.getAnalytics(),
        api.getOrders(),
        api.getProducts(),
        api.getAuditLogs(30),
      ]);
      setAnalytics(stats);
      setOrders(allOrders);
      setProducts(allProducts);
      setAuditLogs(logs);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAdminData();
  }, [loadAdminData]);

  const handleStatusChange = async (orderId: string, status: Order["status"]) => {
    try {
      await api.updateOrderStatus(orderId, status);
      setBanner(`Updated order ${orderId} to ${status}.`);
      await loadAdminData();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to update order");
    }
  };

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const saved = await api.upsertProduct({
        id: "",
        name: name.trim(),
        category: category.trim(),
        price_pkr: Number(pricePkr),
        sizes: sizes.trim(),
        color: color.trim(),
        stock: Number(stock),
        description: description.trim() || `${name.trim()} by Khaas Studio.`,
        upsell_with: upsellWith.trim(),
      });
      setBanner(`Saved product ${saved.id} (${saved.name}).`);
      setName("");
      setDescription("");
      await loadAdminData();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to save product");
    }
  };

  const handleBulkUpload = async () => {
    const trimmed = bulkText.trim();
    if (!trimmed) return;
    try {
      let items: Array<Omit<Product, "created_at">> = [];
      if (trimmed.startsWith("[")) {
        items = JSON.parse(trimmed);
      } else {
        // Parse CSV lines: name,category,price_pkr,sizes,color,stock,description,upsell_with
        items = trimmed
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter((line) => line && !line.toLowerCase().startsWith("name,"))
          .map((line) => {
            const cols = parseCsvLine(line);
            return {
              id: "",
              name: cols[0] || "Untitled Product",
              category: cols[1] || "Kurtas",
              price_pkr: Number(cols[2]) || 3500,
              sizes: cols[3] || "S, M, L",
              color: cols[4] || "Assorted",
              stock: Number(cols[5]) || 10,
              description: cols[6] || "Imported catalog item.",
              upsell_with: cols[7] || "",
            };
          });
      }
      const res = await api.bulkProducts(items);
      setBanner(`Bulk imported ${res.inserted} product(s).`);
      setBulkText("");
      await loadAdminData();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Invalid JSON or CSV format");
    }
  };

  const handleBulkFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      setBulkText(text);
      setBanner(`Loaded ${file.name}. Review and click "Import Items" to save.`);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to read uploaded file");
    } finally {
      e.target.value = "";
    }
  };

  const handleDeleteProduct = async (id: string) => {
    try {
      await api.deleteProduct(id);
      setBanner(`Deleted product ${id}.`);
      await loadAdminData();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Failed to delete product");
    }
  };

  return (
    <div className="min-h-screen bg-[#fafaf7] pb-12">
      {/* Header */}
      <header className="border-b border-stone-200 bg-white sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="px-2.5 py-1.5 rounded-lg border border-stone-200 text-xs font-medium text-stone-700 hover:bg-stone-100 inline-flex items-center gap-1"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Storefront
            </Link>
            <div>
              <h1 className="font-semibold text-lg">Khaas Studio — Seller Admin Dashboard</h1>
              <p className="text-xs text-stone-500">Live Orders, Catalog Management & Agent Guardrail Logs</p>
            </div>
          </div>
          <button
            onClick={loadAdminData}
            className="px-3 py-1.5 rounded-lg bg-emerald-800 hover:bg-emerald-900 text-white text-xs font-medium inline-flex items-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {banner && (
          <div className="px-4 py-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center justify-between">
            <span>{banner}</span>
            <button onClick={() => setBanner("")} className="font-semibold hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {/* KPI Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
            <div className="flex items-center justify-between text-xs text-stone-500">
              <span>Active Revenue</span>
              <Coins className="h-4 w-4 text-emerald-700" />
            </div>
            <div className="text-2xl font-bold mt-1">
              PKR {(analytics?.total_revenue_pkr ?? 0).toLocaleString()}
            </div>
            <div className="text-[11px] text-stone-500 mt-1">
              From {analytics?.active_orders ?? 0} non-cancelled order(s)
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
            <div className="flex items-center justify-between text-xs text-stone-500">
              <span>Total Orders</span>
              <ShoppingBag className="h-4 w-4 text-emerald-700" />
            </div>
            <div className="text-2xl font-bold mt-1">{analytics?.total_orders ?? 0}</div>
            <div className="text-[11px] text-stone-500 mt-1">Across all isolated shoppers</div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
            <div className="flex items-center justify-between text-xs text-stone-500">
              <span>Inventory Health</span>
              <AlertTriangle className="h-4 w-4 text-amber-600" />
            </div>
            <div className="text-2xl font-bold mt-1">{analytics?.low_stock_products ?? 0} Low Stock</div>
            <div className="text-[11px] text-stone-500 mt-1">
              Out of {analytics?.total_products ?? 0} catalog SKUs
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-sm">
            <div className="flex items-center justify-between text-xs text-stone-500">
              <span>Agent Cost & Safety</span>
              <ShieldAlert className="h-4 w-4 text-emerald-700" />
            </div>
            <div className="text-2xl font-bold mt-1">
              {((analytics?.total_tokens_in ?? 0) + (analytics?.total_tokens_out ?? 0)).toLocaleString()} tok
            </div>
            <div className="text-[11px] text-stone-500 mt-1">
              {analytics?.safety_blocks ?? 0} attack(s) blocked at 0 tokens
            </div>
          </div>
        </section>

        {/* Orders Table */}
        <section className="bg-white rounded-xl border border-stone-200 shadow-sm p-4 space-y-3">
          <h2 className="font-semibold text-base flex items-center gap-2">
            <PackageCheck className="h-4 w-4 text-emerald-700" />
            Customer Orders
          </h2>
          {orders.length === 0 ? (
            <p className="text-xs text-stone-500">No orders placed yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-stone-200 text-stone-500">
                    <th className="py-2 pr-3">Order ID</th>
                    <th className="py-2 pr-3">Customer</th>
                    <th className="py-2 pr-3">Item</th>
                    <th className="py-2 pr-3">Total (PKR)</th>
                    <th className="py-2 pr-3">Delivery Address</th>
                    <th className="py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.id} className="border-b border-stone-100">
                      <td className="py-2.5 pr-3 font-mono font-semibold">{o.id}</td>
                      <td className="py-2.5 pr-3 font-mono text-emerald-800">{o.user_id}</td>
                      <td className="py-2.5 pr-3">
                        {o.quantity}x {o.product_name} (Size {o.size})
                      </td>
                      <td className="py-2.5 pr-3 font-semibold">{o.total_pkr.toLocaleString()}</td>
                      <td className="py-2.5 pr-3 text-stone-600">{o.delivery_address}</td>
                      <td className="py-2.5">
                        <select
                          value={o.status}
                          onChange={(e) =>
                            handleStatusChange(o.id, e.target.value as Order["status"])
                          }
                          className="px-2 py-1 rounded border border-stone-200 bg-white text-xs capitalize"
                        >
                          {ORDER_STATUSES.map((st) => (
                            <option key={st} value={st}>
                              {st}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Add Product + Bulk Upload */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <form
            onSubmit={handleAddProduct}
            className="bg-white rounded-xl border border-stone-200 shadow-sm p-4 space-y-3"
          >
            <h2 className="font-semibold text-base flex items-center gap-1.5">
              <Plus className="h-4 w-4 text-emerald-700" />
              Add Catalog Product
            </h2>
            <div className="grid grid-cols-2 gap-2.5 text-xs">
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Product Name"
                className="col-span-2 px-3 py-2 rounded-lg border border-stone-200"
              />
              <input
                required
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="Category"
                className="px-3 py-2 rounded-lg border border-stone-200"
              />
              <input
                required
                type="number"
                min={1}
                value={pricePkr}
                onChange={(e) => setPricePkr(e.target.value)}
                placeholder="Price (PKR)"
                className="px-3 py-2 rounded-lg border border-stone-200"
              />
              <input
                value={sizes}
                onChange={(e) => setSizes(e.target.value)}
                placeholder="Sizes (e.g. S, M, L)"
                className="px-3 py-2 rounded-lg border border-stone-200"
              />
              <input
                value={color}
                onChange={(e) => setColor(e.target.value)}
                placeholder="Color"
                className="px-3 py-2 rounded-lg border border-stone-200"
              />
              <input
                required
                type="number"
                min={0}
                value={stock}
                onChange={(e) => setStock(e.target.value)}
                placeholder="Stock"
                className="px-3 py-2 rounded-lg border border-stone-200"
              />
              <input
                value={upsellWith}
                onChange={(e) => setUpsellWith(e.target.value)}
                placeholder="Upsell SKUs (e.g. KS-201)"
                className="px-3 py-2 rounded-lg border border-stone-200"
              />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Short description"
                rows={2}
                className="col-span-2 px-3 py-2 rounded-lg border border-stone-200"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-emerald-800 hover:bg-emerald-900 text-white text-xs font-medium"
            >
              Save Product
            </button>
          </form>

          <div className="bg-white rounded-xl border border-stone-200 shadow-sm p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold text-base flex items-center gap-1.5">
                <Upload className="h-4 w-4 text-emerald-700" />
                Bulk Catalog Upload (CSV or JSON)
              </h2>
              <label className="px-2.5 py-1 rounded-lg border border-stone-200 hover:bg-stone-100 text-xs font-medium cursor-pointer">
                Choose .csv / .json
                <input
                  type="file"
                  accept=".csv,.json,text/csv,application/json"
                  onChange={handleBulkFileChange}
                  className="hidden"
                />
              </label>
            </div>
            <p className="text-xs text-stone-500">
              Upload a file or paste CSV rows (supports quoted commas like <code>&quot;S, M, L&quot;</code>) or a JSON array.
            </p>
            <textarea
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              rows={6}
              placeholder='Mint Organza Dupatta,Dupattas & Shawls,2100,"One Size",Mint,12,Lightweight festive dupatta'
              className="w-full px-3 py-2 rounded-lg border border-stone-200 text-xs font-mono"
            />
            <button
              onClick={handleBulkUpload}
              disabled={!bulkText.trim()}
              className="px-4 py-2 rounded-lg bg-stone-900 hover:bg-stone-800 disabled:opacity-50 text-white text-xs font-medium"
            >
              Import Items
            </button>
          </div>
        </section>

        {/* Product Inventory Table */}
        <section className="bg-white rounded-xl border border-stone-200 shadow-sm p-4 space-y-3">
          <h2 className="font-semibold text-base">Live Store Inventory ({products.length} SKUs)</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-stone-200 text-stone-500">
                  <th className="py-2 pr-3">SKU</th>
                  <th className="py-2 pr-3">Name</th>
                  <th className="py-2 pr-3">Category</th>
                  <th className="py-2 pr-3">Price</th>
                  <th className="py-2 pr-3">Stock</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id} className="border-b border-stone-100">
                    <td className="py-2 pr-3 font-mono">{p.id}</td>
                    <td className="py-2 pr-3 font-medium">{p.name}</td>
                    <td className="py-2 pr-3">{p.category}</td>
                    <td className="py-2 pr-3">PKR {p.price_pkr.toLocaleString()}</td>
                    <td className="py-2 pr-3">{p.stock}</td>
                    <td className="py-2">
                      <button
                        onClick={() => handleDeleteProduct(p.id)}
                        className="text-red-600 hover:text-red-800 inline-flex items-center gap-1"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Audit & Safety Logs */}
        <section className="bg-white rounded-xl border border-stone-200 shadow-sm p-4 space-y-3">
          <h2 className="font-semibold text-base">Agent Audit & Safety Guardrail Logs</h2>
          {auditLogs.length === 0 ? (
            <p className="text-xs text-stone-500">No agent activity recorded yet.</p>
          ) : (
            <div className="space-y-1.5 max-h-72 overflow-y-auto text-xs">
              {auditLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-stone-50 border border-stone-100"
                >
                  <div className="space-x-2">
                    <span
                      className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-semibold ${
                        log.event_type === "safety_blocked"
                          ? "bg-red-100 text-red-700"
                          : "bg-emerald-100 text-emerald-800"
                      }`}
                    >
                      {log.event_type}
                    </span>
                    <span className="font-mono text-stone-700">{log.user_id}</span>
                    <span className="text-stone-600">{log.detail}</span>
                  </div>
                  <span className="text-[10px] font-mono text-stone-500">
                    {log.tokens_in}in/{log.tokens_out}out · {log.created_at}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
