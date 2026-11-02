"use client";

import { useEffect, useState } from "react";
import { DishImage } from "@/components/dish-image";
import { Button, Chip, PageHead, Section, card, input } from "@/components/ui";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import { budgetLabel } from "@/lib/labels";
import type { Budget, Cluster, Dish, UserProfile } from "@/lib/types";

const diets: Record<UserProfile["diet"], string> = { "binh-thuong": "Bình thường", chay: "Ăn chay", "it-tinh-bot": "Ít tinh bột" };
const spicyLabel = ["Không cay", "Hơi cay", "Cay vừa", "Rất cay"];

export default function ProfilePage() {
  const { data } = useFetch<{ profile: UserProfile; affinity: Record<number, number> }>("/api/profile");
  const meta = useFetch<{ clusters: Cluster[]; dishes: Dish[] }>("/api/clusters");
  const [p, setP] = useState<UserProfile | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setP(data.profile);
  }, [data]);

  if (!p) return <PageHead title="Khẩu vị của bạn" />;

  const allTags = [...new Set((meta.data?.dishes ?? []).flatMap((d) => d.tags))].sort((a, b) => a.localeCompare(b, "vi"));
  const affinity = data?.affinity ?? {};
  const maxAff = Math.max(1, ...Object.values(affinity).map(Math.abs));
  const set = <K extends keyof UserProfile>(k: K, v: UserProfile[K]) => { setP({ ...p, [k]: v }); setSaved(false); };
  const toggleLike = (id: number) =>
    set("likedItemIds", p.likedItemIds.includes(id) ? p.likedItemIds.filter((x) => x !== id) : [...p.likedItemIds, id]);
  const mains = (meta.data?.dishes ?? []).filter((d) => d.categoryId !== null && d.categoryId !== 6);

  async function save() {
    await api.put("/api/profile", { name: p!.name, team: p!.team, diet: p!.diet, avoid: p!.avoid, spicy: p!.spicy, budget: p!.budget, likedItemIds: p!.likedItemIds });
    setSaved(true);
  }

  return (
    <>
      <PageHead title="Khẩu vị của bạn" sub={`${p.name} · ${p.team}`}>
        <Button variant="primary" onClick={save}>{saved ? "Đã lưu" : "Lưu khẩu vị"}</Button>
      </PageHead>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className={`${card} flex flex-col gap-5 p-5`}>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Tên hiển thị</span>
            <input id="profile-name" className={input} value={p.name} onChange={(e) => set("name", e.target.value)} />
          </label>
          <div className="flex flex-col gap-2 text-sm">
            <span className="text-muted">Chế độ ăn</span>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(diets) as UserProfile["diet"][]).map((d) => (
                <Chip key={d} active={p.diet === d} onClick={() => set("diet", d)}>{diets[d]}</Chip>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2 text-sm">
            <span className="text-muted">Độ cay: <b className="text-ink">{spicyLabel[p.spicy]}</b></span>
            <input
              id="profile-spicy"
              type="range" min={0} max={3} step={1} value={p.spicy}
              onChange={(e) => set("spicy", Number(e.target.value) as UserProfile["spicy"])}
              className="accent-[var(--bad)]"
            />
          </div>
          <div className="flex flex-col gap-2 text-sm">
            <span className="text-muted">Ngân sách thường ngày</span>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(budgetLabel) as Budget[]).map((b) => (
                <Chip key={b} active={p.budget === b} onClick={() => set("budget", b)}>{budgetLabel[b]}</Chip>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-2 text-sm">
            <span className="text-muted">Không ăn được ({p.avoid.length})</span>
            <div className="flex flex-wrap gap-2">
              {allTags.map((t) => (
                <Chip
                  key={t}
                  active={p.avoid.includes(t)}
                  onClick={() => set("avoid", p.avoid.includes(t) ? p.avoid.filter((x) => x !== t) : [...p.avoid, t])}
                >
                  {t}
                </Chip>
              ))}
            </div>
          </div>
        </div>

        <div className={`${card} p-5`}>
          <h2 className="text-lg font-semibold">Bạn hợp nhóm món nào</h2>
          <p className="mb-4 text-sm text-muted">Tính từ lịch sử: mỗi bữa yes cộng điểm, mỗi bữa no trừ điểm cho cụm của món đó.</p>
          <ul className="flex flex-col gap-3">
            {(meta.data?.clusters ?? []).map((c) => {
              const v = affinity[c.id] ?? 0;
              return (
                <li key={c.id} className="grid grid-cols-[9rem_1fr_2.5rem] items-center gap-3 text-sm">
                  <span className="truncate">{c.name}</span>
                  <div className="relative h-2 rounded-full bg-surface-2">
                    <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
                    <div
                      className="absolute inset-y-0 rounded-full"
                      style={{
                        background: v >= 0 ? c.color : "var(--bad)",
                        left: v >= 0 ? "50%" : `${50 - (Math.abs(v) / maxAff) * 50}%`,
                        width: `${(Math.abs(v) / maxAff) * 50}%`,
                      }}
                    />
                  </div>
                  <span className="text-right tabular-nums text-muted">{v > 0 ? `+${v}` : v}</span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <div className="mt-10">
        <Section
          title={`Món bạn thích (${p.likedItemIds.length})`}
          sub="Dùng làm điểm xuất phát khi bạn chưa có lịch sử: vector khẩu vị ban đầu = trung bình vector các món này (Qdrant recommend, positive)."
        >
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6">
            {mains.map((d) => {
              const on = p.likedItemIds.includes(d.itemId);
              return (
                <button
                  key={d.itemId}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleLike(d.itemId)}
                  className={`overflow-hidden rounded-xl bg-surface text-left ring-2 transition ${on ? "ring-accent" : "ring-transparent hover:ring-line"}`}
                >
                  <DishImage src={d.image} alt="" sizes="(min-width:1024px) 160px, 30vw" className="aspect-square" />
                  <span className={`block truncate px-2 py-1.5 text-xs ${on ? "font-medium text-ink" : "text-muted"}`}>{d.name}</span>
                </button>
              );
            })}
          </div>
        </Section>
      </div>
    </>
  );
}
