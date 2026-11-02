"use client";

import { useState } from "react";
import { ClusterPill, PageHead, card } from "@/components/ui";
import { useFetch } from "@/lib/hooks";
import { formatPrice } from "@/lib/labels";
import type { Cluster, Dish, Meal } from "@/lib/types";

export default function ClustersPage() {
  const { data } = useFetch<{ clusters: Cluster[]; dishes: Dish[] }>("/api/clusters");
  const meals = useFetch<Meal[]>("/api/meals");
  const [active, setActive] = useState<number | null>(null);
  const [hover, setHover] = useState<Dish | null>(null);

  const clusters = data?.clusters ?? [];
  const dishes = (data?.dishes ?? []).filter(d => d.clusterId >= 0 && d.vectorStatus === "synced");
  const eaten = new Set((meals.data ?? []).flatMap((m) => m.itemIds));
  const shown = active === null ? dishes : dishes.filter((d) => d.clusterId === active);

  return (
    <>
      <PageHead
        title="Khám phá cụm món"
        sub="Mỗi chấm là một món, đặt theo vector đã giảm xuống 2 chiều. PCA có thể làm biến dạng khoảng cách gốc."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className={`${card} min-w-0 p-4`}>
          <div className="mb-3 flex flex-wrap gap-x-4 gap-y-2">
            <button type="button" onClick={() => setActive(null)} className={`text-xs ${active === null ? "font-semibold text-ink" : "text-muted"}`}>
              Tất cả
            </button>
            {clusters.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setActive(active === c.id ? null : c.id)}
                className={active === null || active === c.id ? "" : "opacity-40"}
              >
                <ClusterPill name={c.name} color={c.color} />
              </button>
            ))}
          </div>

          <div className="relative mx-auto max-w-[36rem]">
            <svg viewBox="0 0 100 100" className="mx-auto aspect-square w-full max-w-[36rem]" preserveAspectRatio="none" role="img" aria-label="Biểu đồ phân cụm món ăn">
              {[20, 40, 60, 80].map((v) => (
                <g key={v} stroke="var(--line)" strokeWidth="0.15">
                  <line x1={v} y1="0" x2={v} y2="100" />
                  <line x1="0" y1={v} x2="100" y2={v} />
                </g>
              ))}
              {dishes.map((d) => {
                const dim = active !== null && d.clusterId !== active;
                const color = clusters[d.clusterId]?.color ?? "var(--muted)";
                return (
                  <g key={d.itemId} onMouseEnter={() => setHover(d)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }} onClick={() => setActive(d.clusterId)}>
                    {eaten.has(d.itemId) && <circle cx={d.x} cy={d.y} r="2.4" fill="none" stroke="var(--ink)" strokeWidth="0.35" opacity={dim ? 0.2 : 1} />}
                    <circle cx={d.x} cy={d.y} r={hover?.itemId === d.itemId ? 2 : 1.4} fill={color} opacity={dim ? 0.15 : 0.9} />
                  </g>
                );
              })}
            </svg>
            {hover && (
              <div
                className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow"
                style={{ left: `${hover.x}%`, top: `calc(${hover.y}% - 10px)` }}
              >
                <div className="font-medium">{hover.name}</div>
                <div className="text-muted">#{hover.itemId} · {formatPrice(hover.price)}</div>
              </div>
            )}
          </div>
          <p className="mt-2 text-xs text-muted">Vòng tròn đen: món bạn đã ăn. Toạ độ PCA và cụm KMeans được tính từ model đã huấn luyện.</p>
        </div>

        <aside className="flex flex-col gap-4">
          {(active === null ? clusters : clusters.filter((c) => c.id === active)).map((c) => {
            const items = shown.filter((d) => d.clusterId === c.id);
            return (
              <div key={c.id} className={`${card} p-4`}>
                <div className="flex items-baseline justify-between">
                  <ClusterPill name={c.name} color={c.color} />
                  <span className="text-xs tabular-nums text-muted">{items.length} món</span>
                </div>
                <p className="mt-1 text-sm text-muted">{c.description}</p>
                {active !== null && (
                  <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                    {items.map((d) => (
                      <li key={d.itemId} className="flex justify-between gap-2">
                        <span>{d.name}</span>
                        <span className="font-mono text-xs text-muted">#{d.itemId}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </aside>
      </div>
    </>
  );
}
