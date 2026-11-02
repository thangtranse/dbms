import { formatPrice } from "@/lib/labels";
import type { Cluster, Recommendation } from "@/lib/types";
import { DishImage } from "./dish-image";
import { Button, ClusterPill } from "./ui";

interface Actions {
  onPick?: () => void;
  onSkip?: () => void;
  onDislike?: () => void;
  picked?: boolean;
}

function Score({ score, predicted }: { score: number | null; predicted: Recommendation["predictedLabel"] }) {
  if (score === null) return <span className="text-xs text-muted">Phổ biến · cold start</span>;
  return (
    <div className="flex items-center gap-2 text-xs text-muted">
      <div className="h-1 w-16 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(0, score) * 100}%` }} />
      </div>
      <span className="tabular-nums">
        Cosine {score.toFixed(3)} ·{" "}
        <span className={predicted === "yes" ? "text-good" : "text-muted"}>{predicted === "yes" ? "dự đoán thích" : "chưa chắc"}</span>
      </span>
    </div>
  );
}

function DrinkLine({ drink, compact }: { drink: NonNullable<Recommendation["drink"]>; compact?: boolean }) {
  return (
    <div className={`flex items-center gap-2.5 ${compact ? "text-xs" : "rounded-xl bg-surface-2 p-2.5 text-sm"}`}>
      {!compact && <DishImage src={drink.dish.image} alt={drink.dish.name} sizes="40px" className="size-10 shrink-0 rounded-lg" />}
      <span className="min-w-0 text-muted">
        {compact ? "Kèm " : "Thường đi kèm "}
        <b className="font-medium text-ink">{drink.dish.name}</b>
        {!compact && <> · {formatPrice(drink.dish.price)}</>}
        <span className="tabular-nums"> ({Math.round(drink.confidence * 100)}% bữa có món này)</span>
      </span>
    </div>
  );
}

// Thẻ lớn cho món nổi bật nhất hôm nay.
export function FeaturedCard({ rec, cluster, ...a }: { rec: Recommendation; cluster?: Cluster } & Actions) {
  const { dish } = rec;
  return (
    <article className={`grid overflow-hidden rounded-3xl bg-surface ring-1 md:grid-cols-[1.15fr_1fr] ${a.picked ? "ring-2 ring-accent" : "ring-line"}`}>
      <DishImage src={dish.image} alt={dish.name} sizes="(min-width:768px) 600px, 100vw" priority className="aspect-[4/3] md:aspect-auto md:min-h-80" />
      <div className="flex flex-col gap-4 p-6 sm:p-8">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wider text-accent">Gợi ý hàng đầu</span>
          {cluster && <ClusterPill name={cluster.name} color={cluster.color} />}
        </div>
        <div>
          <h2 className="text-3xl font-semibold leading-tight">{dish.name}</h2>
          <p className="mt-2 text-muted">{rec.reason}</p>
        </div>
        <div className="flex items-baseline gap-3">
          <span className="text-2xl font-semibold tabular-nums">{formatPrice(dish.price)}</span>
          <Score score={rec.score} predicted={rec.predictedLabel} />
        </div>
        {rec.drink && <DrinkLine drink={rec.drink} />}
        <div className="mt-auto grid grid-cols-2 gap-2 pt-2">
          {a.onPick && (
            <Button variant="primary" className="col-span-2 py-2.5" onClick={a.onPick} disabled={a.picked}>
              {a.picked ? "Đã chọn cho hôm nay" : "Chọn món này"}
            </Button>
          )}
          {a.onSkip && <Button onClick={a.onSkip}>Đổi món</Button>}
          {a.onDislike && <Button variant="danger" onClick={a.onDislike}>Không thích</Button>}
        </div>
      </div>
    </article>
  );
}

// Thẻ nhỏ cho các lựa chọn khác.
export function RecommendationCard({ rec, cluster, rank, ...a }: { rec: Recommendation; cluster?: Cluster; rank: number } & Actions) {
  const { dish } = rec;
  return (
    <article
      className={`rise flex flex-col overflow-hidden rounded-2xl bg-surface ring-1 ${a.picked ? "ring-2 ring-accent" : "ring-line"}`}
      style={{ animationDelay: `${rank * 50}ms` }}
    >
      <DishImage src={dish.image} alt={dish.name} sizes="(min-width:1024px) 320px, (min-width:640px) 45vw, 100vw" className="aspect-[16/10]" />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-center justify-between gap-2">
          {cluster && <ClusterPill name={cluster.name} color={cluster.color} />}
          <span className="font-semibold tabular-nums">{formatPrice(dish.price)}</span>
        </div>
        <h3 className="font-semibold leading-snug">{dish.name}</h3>
        <p className="line-clamp-2 text-sm text-muted">{rec.reason}</p>
        {rec.drink && <DrinkLine drink={rec.drink} compact />}
        <div className="mt-auto pt-2">
          <Score score={rec.score} predicted={rec.predictedLabel} />
        </div>
        {(a.onPick || a.onSkip || a.onDislike) && (
          <div className="flex gap-1.5 pt-1">
            {a.onPick && (
              <Button variant="primary" className="flex-1" onClick={a.onPick} disabled={a.picked}>
                {a.picked ? "Đã chọn" : "Chọn"}
              </Button>
            )}
            {a.onSkip && <Button variant="quiet" onClick={a.onSkip}>Đổi</Button>}
            {a.onDislike && <Button variant="danger" onClick={a.onDislike} aria-label="Không thích món này">Không thích</Button>}
          </div>
        )}
      </div>
    </article>
  );
}
