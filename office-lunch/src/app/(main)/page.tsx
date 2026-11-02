"use client";

import { useEffect, useState } from "react";
import { ContextPicker } from "@/components/context-picker";
import { FeaturedCard, RecommendationCard } from "@/components/recommendation-card";
import { Button, Section, card } from "@/components/ui";
import { useUser } from "@/components/user-context";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import type { Cluster, Dish, LunchContext, Meal, Recommendation, WeatherNow } from "@/lib/types";

const cities = { hcm: "TP.HCM", hn: "Hà Nội", dn: "Đà Nẵng" } as const;
type City = keyof typeof cities;

export default function HomePage() {
  const { user } = useUser();
  const [ctx, setCtx] = useState<LunchContext>({ weather: "nang-nong", budget: user.budget, breakTime: 30, mood: "gi-cung-duoc", groupSize: 1 });
  const [city, setCity] = useState<City>("hcm");
  const [weather, setWeather] = useState<WeatherNow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [exclude, setExclude] = useState<number[]>([]);
  const [picked, setPicked] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const { data } = useFetch<{ clusters: Cluster[]; dishes: Dish[] }>("/api/clusters");

  // Thời tiết tự động: điền sẵn chip thời tiết, người dùng vẫn đổi tay được.
  useEffect(() => {
    api.get<WeatherNow>(`/api/weather?city=${city}`).then((w) => {
      setWeather(w);
      setCtx((c) => ({ ...c, weather: w.weather }));
    });
  }, [city]);

  useEffect(() => {
    api.post<Recommendation[]>("/api/recommend", { context: ctx, exclude, limit: 4 }).then((r) => { setRecs(r); setError(null); }, (e: Error) => setError(e.message));
  }, [ctx, exclude]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2600);
    return () => clearTimeout(t);
  }, [toast]);

  async function pick(rec: Recommendation) {
    const itemIds = rec.drink ? [rec.dish.itemId, rec.drink.dish.itemId] : [rec.dish.itemId];
    await api.post<Meal>("/api/meals", { date: new Date().toISOString().slice(0, 10), itemIds, label: "yes", context: ctx });
    setPicked(rec.dish.itemId);
    setToast(`Đã lưu "${rec.dish.name}" vào lịch sử hôm nay`);
  }

  async function skip(rec: Recommendation, disliked = false) {
    if (disliked) {
      try {
        await api.post("/api/meals", { date: new Date().toISOString().slice(0, 10), itemIds: [rec.dish.itemId], label: "no", context: ctx });
      } catch (e) { setError((e as Error).message); return; }
    }
    setExclude((e) => [...e, rec.dish.itemId]);
    if (disliked) setToast(`Đã lưu phản hồi không thích "${rec.dish.name}"`);
  }

  const featured = recs?.[0] ?? null;
  const others = recs?.slice(1) ?? [];
  const cluster = (r: Recommendation) => data?.clusters[r.dish.clusterId];
  const now = new Date();
  const today = now.toLocaleDateString("vi-VN", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div className="flex flex-col gap-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm capitalize text-muted">{today}</p>
          <h1 className="mt-1 text-3xl font-semibold sm:text-4xl">
            Chào {user.name.split(" ").at(-1)}, hôm nay ăn gì?
          </h1>
        </div>
        {weather && (
          <div className="flex items-center gap-3 rounded-full bg-surface px-4 py-2 text-sm ring-1 ring-line">
            <span className="text-lg font-semibold tabular-nums">{weather.temperature}°</span>
            <span className="text-muted">{weather.description}</span>
            <select
              id="weather-city"
              aria-label="Thành phố"
              value={city}
              onChange={(e) => setCity(e.target.value as City)}
              className="bg-transparent text-ink focus:outline-none"
            >
              {(Object.keys(cities) as City[]).map((c) => <option key={c} value={c}>{cities[c]}</option>)}
            </select>
          </div>
        )}
      </header>

      <div className={`${card} p-5`}>
        {error && <p role="alert" className="text-sm text-muted">{error}</p>}
      <ContextPicker value={ctx} onChange={(v) => { setCtx(v); setPicked(null); }} autoWeather={weather?.source === "open-meteo" ? weather.weather : undefined} />
      </div>

      {recs && recs.length === 0 && (
        <div className={`${card} p-10 text-center text-muted`}>
          Không có món nào hợp các điều kiện này. Thử nới ngân sách hoặc{" "}
          <button type="button" className="text-accent underline" onClick={() => setExclude([])}>bỏ các món đã bỏ qua</button>.
        </div>
      )}

      {featured && (
        <Section
          title="Món nổi bật hôm nay"
          aside={exclude.length > 0 && <Button variant="quiet" onClick={() => setExclude([])}>Gợi ý lại từ đầu</Button>}
        >
          <FeaturedCard
            rec={featured}
            cluster={cluster(featured)}
            picked={picked === featured.dish.itemId}
            onPick={() => pick(featured)}
            onSkip={() => skip(featured)}
            onDislike={() => skip(featured, true)}
          />
        </Section>
      )}

      {others.length > 0 && (
        <Section title="Lựa chọn khác" sub="Độ hợp = tương đồng cosine giữa vector khẩu vị của bạn và vector món (Qdrant).">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {others.map((r, i) => (
              <RecommendationCard
                key={r.dish.itemId}
                rec={r}
                rank={i}
                cluster={cluster(r)}
                picked={picked === r.dish.itemId}
                onPick={() => pick(r)}
                onSkip={() => skip(r)}
              />
            ))}
          </div>
        </Section>
      )}

      {toast && (
        <div
          role="status"
          className="fixed bottom-[calc(1.5rem+env(safe-area-inset-bottom,0px))] left-1/2 z-30 -translate-x-1/2 rounded-full bg-ink px-4 py-2 text-sm text-bg shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
