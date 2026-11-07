"use client";

import { useRef, useState } from "react";
import { DishImage } from "@/components/dish-image";
import { Button, ClusterPill, PageHead, card, input } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { formatPrice } from "@/lib/labels";
import type { Cluster, Dish } from "@/lib/types";


type Draft = { itemId: string; name: string; categoryId: number; price: string; tags: string; image: string };
const empty: Draft = { itemId: "", name: "", categoryId: 0, price: "", tags: "", image: "" };

const pageSize = 25;

export default function DishesPage() {
  const { data, reload } = useFetch<{ categories: Cluster[]; dishes: Dish[] }>("/api/clusters");
  const listRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<number | "all">("all");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const clusters = data?.categories ?? [];
  const total = data?.dishes.length ?? 0;
  const named = (data?.dishes ?? []).filter((d) => d.source !== "unmapped" && !d.name.startsWith("Item #")).length;
  const rows = (data?.dishes ?? [])
    .filter((d) => filter === "all" || d.categoryId === filter)
    .filter((d) => `${d.name} ${d.itemId}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => (a.categoryId ?? 99) - (b.categoryId ?? 99) || a.name.localeCompare(b.name, "vi"));

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const offset = (currentPage - 1) * pageSize;
  const pageRows = rows.slice(offset, offset + pageSize);

  function goToPage(nextPage: number) {
    setPage(nextPage);
    setConfirmId(null);
    listRef.current?.scrollIntoView({ block: "start" });
  }

  function edit(d: Dish) {
    setEditingId(d.itemId);
    setDraft({ itemId: String(d.itemId), name: d.name, categoryId: d.categoryId ?? 0, price: String(d.price), tags: d.tags.join(", "), image: d.image });
  }

  async function save() {
    if (!draft) return;
    const body = {
      itemId: Number(draft.itemId),
      name: draft.name.trim(),
      categoryId: draft.categoryId,
      price: Number(draft.price),
      tags: draft.tags.split(",").map((t) => t.trim()).filter(Boolean),
      image: draft.image.trim().split("?")[0],
    };
    if (!body.itemId || !body.name || !body.price) return setError("Cần nhập mã món, tên món và giá.");
    try {
      if (editingId) await api.put(`/api/dishes/${editingId}`, body);
      else await api.post("/api/dishes", body); // toạ độ thật do backend tính lại
      setDraft(null);
      setEditingId(null);
      setError(null);
      reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove(id: number) {
    await api.del(`/api/dishes/${id}`);
    setConfirmId(null);
    reload();
  }

  const field = (k: keyof Draft, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="text-muted">{label}</span>
      <input
        id={`dish-${k}`}
        className={input}
        value={draft?.[k] as string}
        onChange={(e) => setDraft((d) => d && { ...d, [k]: e.target.value })}
        {...props}
      />
    </label>
  );

  return (
    <>
      <PageHead
        title="Quản lý món"
        sub="Tên và ảnh công thức có dẫn nguồn; ánh xạ sang mã nghiên cứu là demo. Giá chưa xác minh để trống; cụm học máy được tính riêng."
      >
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={() => { setEditingId(null); setDraft(empty); }}>Thêm món</Button>
        </div>
      </PageHead>

      <div className={`${card} mb-6 flex flex-col gap-2 p-4`}>
        <div className="flex items-baseline justify-between text-sm">
          <span>Đã gán tên</span>
          <span className="tabular-nums text-muted">
            <b className="text-ink">{named}</b> / {total} mã món
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-surface-2">
          <div className="h-full bg-accent" style={{ width: `${(total ? named / total : 0) * 100}%` }} />
        </div>
      </div>

      {draft && (
        <div className={`${card} mb-6 flex flex-col gap-4 p-5`}>
          <h2 className="text-lg font-semibold">{editingId ? `Sửa món #${editingId}` : "Thêm món"}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {field("itemId", "Mã món (item_id)", { inputMode: "numeric", disabled: !!editingId })}
            {field("name", "Tên món")}
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-muted">Cụm</span>
              <select
                id="dish-cluster"
                className={input}
                value={draft.categoryId}
                onChange={(e) => setDraft({ ...draft, categoryId: Number(e.target.value) })}
              >
                {clusters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            {field("price", "Giá (VND)", { inputMode: "numeric" })}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {field("tags", "Tag, cách nhau bằng dấu phẩy", { placeholder: "nước, nóng, bò" })}
            {field("image", "URL ảnh (images.unsplash.com/…)", { placeholder: "https://images.unsplash.com/photo-…" })}
          </div>
          {draft.image.startsWith("https://images.unsplash.com/") && (
            <DishImage src={draft.image.split("?")[0]} alt="Xem trước ảnh món" sizes="240px" className="aspect-[4/3] w-60 max-w-full rounded-xl" />
          )}
          {error && <p className="text-sm text-bad">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button onClick={() => { setDraft(null); setError(null); }}>Huỷ</Button>
            <Button variant="primary" onClick={save}>Lưu</Button>
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        <input id="dish-search" className={`${input} sm:max-w-xs`} placeholder="Tìm theo tên hoặc mã…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <select
          id="dish-filter"
          className={`${input} sm:max-w-xs`}
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value === "all" ? "all" : Number(e.target.value));
            setPage(1);
          }}
        >
          <option value="all">Tất cả cụm</option>
          {clusters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      <div ref={listRef} className={`${card} overflow-x-auto`}>
        <table className="w-full min-w-[40rem] text-sm">
          <thead className="border-b border-line text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Mã</th>
              <th className="px-4 py-3 font-medium">Tên món</th>
              <th className="px-4 py-3 font-medium">Cụm</th>
              <th className="px-4 py-3 text-right font-medium">Giá</th>
              <th className="px-4 py-3 font-medium">Tag</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {data && pageRows.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-muted">Không tìm thấy món.</td></tr>
            )}
            {pageRows.map((d) => (
              <tr key={d.itemId} className="border-b border-line last:border-0">
                <td className="px-4 py-2.5 font-mono text-muted">{d.itemId}</td>
                <td className="px-4 py-2.5 font-medium">
                  <span className="flex items-center gap-3">
                    <DishImage src={d.image} alt="" sizes="36px" className="size-9 shrink-0 rounded-lg" />
                    <span>
                      {d.name}
                      {d.sourceUrl && <a href={d.sourceUrl} target="_blank" rel="noreferrer" className="block text-xs text-muted underline">Nguồn: {d.sourceProvider} · ánh xạ demo</a>}
                    </span>
                    {d.vectorStatus === "pending" && <span className="ml-2 text-xs text-muted">Chờ vector</span>}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  {clusters[d.categoryId ?? -1] && <ClusterPill name={clusters[d.categoryId ?? -1].name} color={clusters[d.categoryId ?? -1].color} />}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">{d.price <= 0 ? "Chưa có giá" : formatPrice(d.price)}</td>
                <td className="px-4 py-2.5 text-muted">{d.tags.join(", ")}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  {confirmId === d.itemId ? (
                    <span className="inline-flex gap-2">
                      <Button variant="danger" onClick={() => remove(d.itemId)}>Xoá thật</Button>
                      <Button onClick={() => setConfirmId(null)}>Không</Button>
                    </span>
                  ) : (
                    <span className="inline-flex gap-2">
                      <Button onClick={() => edit(d)}>Sửa</Button>
                      <Button variant="danger" onClick={() => setConfirmId(d.itemId)}>Xoá</Button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 0 && (
        <nav aria-label="Phân trang danh sách món" className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
          <p className="text-muted" aria-live="polite">
            Hiển thị {offset + 1}–{offset + pageRows.length} / {rows.length} món
          </p>
          <div className="flex items-center gap-2">
            <Button disabled={currentPage === 1} onClick={() => goToPage(currentPage - 1)}>Trang trước</Button>
            <span className="tabular-nums">Trang {currentPage} / {pageCount}</span>
            <Button disabled={currentPage === pageCount} onClick={() => goToPage(currentPage + 1)}>Trang sau</Button>
          </div>
        </nav>
      )}
    </>
  );
}
