"use client";

import { useState } from "react";
import { MealForm } from "@/components/meal-form";
import { Button, ClusterPill, LabelBadge, PageHead, card } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { formatDate, formatPrice, toTransactionLine } from "@/lib/labels";
import type { Cluster, Dish, Meal } from "@/lib/types";

export default function HistoryPage() {
  const meals = useFetch<Meal[]>("/api/meals");
  const meta = useFetch<{ clusters: Cluster[]; dishes: Dish[] }>("/api/clusters");
  const [editing, setEditing] = useState<Meal | "new" | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const dishes = meta.data?.dishes ?? [];
  const byId = new Map(dishes.map((d) => [d.itemId, d]));
  const list = meals.data ?? [];
  const yesRate = list.length ? Math.round((list.filter((m) => m.label === "yes").length / list.length) * 100) : 0;

  async function save(m: Pick<Meal, "date" | "itemIds" | "label">) {
    if (editing === "new") await api.post("/api/meals", m);
    else if (editing) await api.put(`/api/meals/${editing.id}`, m);
    setEditing(null);
    meals.reload();
  }

  async function remove(id: string) {
    await api.del(`/api/meals/${id}`);
    setConfirmId(null);
    meals.reload();
  }

  async function flip(m: Meal) {
    await api.put(`/api/meals/${m.id}`, { label: m.label === "yes" ? "no" : "yes" });
    meals.reload();
  }

  return (
    <>
      <PageHead
        title="Lịch sử bữa trưa"
        sub="Mỗi bữa được lưu thành một giao dịch giống một dòng trong food.txt. Nhãn yes/no dùng để huấn luyện phân loại."
      >
        <Button variant="primary" onClick={() => setEditing("new")}>Thêm bữa ăn</Button>
      </PageHead>

      <div className="mb-6 grid grid-cols-3 gap-3 sm:max-w-lg">
        {[
          ["Số bữa", list.length],
          ["Tỉ lệ hài lòng", `${yesRate}%`],
          ["Món khác nhau", new Set(list.flatMap((m) => m.itemIds)).size],
        ].map(([k, v]) => (
          <div key={k} className={`${card} p-3`}>
            <div className="text-xs text-muted">{k}</div>
            <div className="text-2xl font-semibold tabular-nums">{v}</div>
          </div>
        ))}
      </div>

      {editing && (
        <div className={`${card} mb-6 p-5`}>
          <h2 className="mb-4 text-lg font-semibold">{editing === "new" ? "Thêm bữa ăn" : "Sửa bữa ăn"}</h2>
          <MealForm
            key={editing === "new" ? "new" : editing.id}
            dishes={dishes}
            initial={editing === "new" ? undefined : editing}
            onSubmit={save}
            onCancel={() => setEditing(null)}
          />
        </div>
      )}

      <ol className="flex flex-col gap-3">
        {list.map((m) => {
          const ds = m.itemIds.map((id) => byId.get(id)).filter(Boolean) as Dish[];
          const total = ds.reduce((s, d) => s + d.price, 0);
          return (
            <li key={m.id} className={`${card} flex flex-col gap-3 p-4 sm:flex-row sm:items-center`}>
              <div className="w-24 shrink-0 text-sm capitalize text-muted">{formatDate(m.date)}</div>
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <div className="font-medium">{ds.map((d) => d.name).join(" + ") || "—"}</div>
                {m.vectorStatus === "pending" && <p className="text-xs text-muted">Đã lưu · đang đồng bộ gợi ý</p>}
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {[...new Set(ds.map((d) => d.clusterId))].map((id) => {
                    const cluster = meta.data?.clusters.find((c) => c.id === id);
                    return cluster ? <ClusterPill key={id} name={cluster.name} color={cluster.color} /> : null;
                  })}
                  <code className="overflow-x-auto whitespace-pre font-mono text-xs text-muted">
                    {toTransactionLine(m.label, m.itemIds)}
                  </code>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="w-12 text-right font-medium tabular-nums">{formatPrice(total)}</span>
                <button type="button" onClick={() => flip(m)} title="Đổi nhãn yes/no">
                  <LabelBadge label={m.label} />
                </button>
                {confirmId === m.id ? (
                  <>
                    <Button variant="danger" onClick={() => remove(m.id)}>Xoá thật</Button>
                    <Button onClick={() => setConfirmId(null)}>Không</Button>
                  </>
                ) : (
                  <>
                    <Button onClick={() => setEditing(m)}>Sửa</Button>
                    <Button variant="danger" onClick={() => setConfirmId(m.id)}>Xoá</Button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </>
  );
}
