// Kiểu dữ liệu dùng chung giữa UI và API.
// Dish/Meal/UserProfile nằm ở Teradata,
// vector + cluster_id của Dish/Meal nằm ở Qdrant (payload).

export type Label = "yes" | "no";

export interface Cluster {
  id: number;
  name: string;
  description: string;
  color: string; // màu hiển thị trên biểu đồ (CSS color)
}

export interface Dish {
  itemId: number; // mã món gốc trong food.txt (Trans2Vec)
  name: string;
  source?: string;
  metadataVersion?: string;
  sourceUrl?: string;
  sourceProvider?: string;
  mappingBasis?: string;
  priceStatus?: "unknown";
  categoryId: number | null; // metadata demo
  clusterId: number; // cụm học máy, -1 khi chưa có vector
  vectorStatus?: "pending" | "synced";
  modelVersion?: string | null;
  price: number; // VND
  tags: string[];
  image: string; // URL ảnh (Unsplash), không kèm query string
  // Toạ độ 2D sau khi giảm chiều vector (PCA) — pipeline tính từ vector
  x: number;
  y: number;
}

export type Weather = "nang-nong" | "mua" | "mat";
export type Budget = "duoi-35" | "35-50" | "tren-50";
export type BreakTime = 15 | 30 | 60;
export type Mood = "an-nhe" | "no-bung" | "healthy" | "gi-cung-duoc";

export interface LunchContext {
  weather: Weather;
  budget: Budget;
  breakTime: BreakTime;
  mood: Mood;
  groupSize: number;
}

// Một bữa ăn = một giao dịch (transaction) giống một dòng trong food.txt:
// "<label>\t<itemId> <itemId> ..."
export interface Meal {
  vectorStatus?: "pending" | "synced";
  source?: string;
  id: string;
  userId: string;
  date: string; // ISO yyyy-mm-dd
  itemIds: number[];
  label: Label;
  context?: LunchContext;
}

export interface Recommendation {
  dish: Dish;
  score: number | null; // cosine -1..1; null khi cold start
  reason: string;
  predictedLabel: Label; // kết quả phân loại kNN yes/no
  // Đồng xuất hiện trên food, kết hợp category đồ uống do demo gán
  drink?: { dish: Dish; confidence: number };
}

export interface UserProfile {
  id: string;
  name: string;
  team: string;
  diet: "binh-thuong" | "chay" | "it-tinh-bot";
  avoid: string[];
  spicy: 0 | 1 | 2 | 3;
  budget: Budget;
  likedItemIds: number[]; // món tự đánh dấu thích, dùng khi chưa có lịch sử (cold start)
}

export interface WeatherNow {
  city: string;
  temperature: number;
  description: string;
  weather: Weather;
  source: "open-meteo" | "fallback";
}

export interface Stats {
  totalMeals: number;
  spendThisWeek: number;
  yesRate: number;
  favorite?: { dish: Dish; count: number };
  weeklySpend: { week: string; amount: number }[];
  topDishes: { dish: Dish; count: number }[];
  clusterYes: { clusterId: number; yes: number; no: number }[];
}
