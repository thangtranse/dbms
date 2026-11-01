# OfficeLunch — Hôm nay ăn gì?

Gợi ý món ăn trưa theo ngữ cảnh. Teradata lưu dữ liệu (CRUD), Qdrant lưu vector và lo phân cụm/phân loại.
Dataset: `food` của [Trans2Vec](https://github.com/nphdang/Trans2Vec/tree/main/datasets/food)
(4000 giao dịch, 2000 yes / 2000 no, 1559 mã món, trung bình 26,6 món/giao dịch).

Giai đoạn hiện tại: **chỉ có UI, dùng dữ liệu giả** (trừ thời tiết lấy thật từ Open-Meteo).

```bash
npm install
npm run dev
```

## Màn hình

Menu chia theo 2 môn.

**Ứng dụng (CSDL nâng cao: Teradata + Qdrant)**

| Đường dẫn  | Màn hình       | Teradata                              | Qdrant                                         |
|------------|----------------|---------------------------------------|------------------------------------------------|
| `/`        | Hôm nay ăn gì  | hồ sơ, lịch sử, luật kết hợp đồ uống  | recommend theo món thích + lọc payload, kNN yes/no |
| `/history` | Lịch sử        | CRUD `meals`, `meal_items`            | upsert / xoá vector giao dịch                  |
| `/stats`   | Thống kê       | truy vấn tổng hợp (GROUP BY, TRUNC)   | –                                              |
| `/dishes`  | Quản lý món    | CRUD `dishes`                         | cập nhật payload món                           |
| `/profile` | Khẩu vị        | `users`, `user_avoid`, `user_likes`   | món thích = positive cho recommend             |

**Thực nghiệm Trans2Vec (KDD)**

| Đường dẫn     | Màn hình          | Nội dung                                              |
|---------------|-------------------|-------------------------------------------------------|
| `/clusters`   | Khám phá cụm      | vector món giảm về 2D, tô màu theo cụm               |
| `/evaluation` | Đánh giá mô hình  | so sánh phương pháp, ảnh hưởng minsup, ma trận nhầm lẫn (hiện là số giả) |

Nút **Xem truy vấn** (góc dưới phải) liệt kê các câu SQL Teradata và truy vấn Qdrant mà trang vừa gọi.
Hiện là câu truy vấn mẫu; khi nối backend thật thì thay bằng truy vấn đã chạy.

Có 3 người dùng mẫu, đổi ở thanh bên (không có đăng nhập).

## Cấu trúc

```
src/
  app/(main)/       các trang (có thanh bên + khung Xem truy vấn)
  app/api/*         route handlers
  components/       UI dùng chung
  lib/types.ts      kiểu dữ liệu (hợp đồng giữa UI và API)
  lib/mock-data.ts  dữ liệu giả; itemId lấy từ food.txt, ảnh từ Unsplash
  lib/store.ts      kho dữ liệu trong bộ nhớ + thuật toán gợi ý giả
  lib/evaluation.ts kết quả đánh giá mô hình giả lập
  lib/api.ts        client gọi API (UI chỉ đi qua file này)
  lib/query-log.ts  ghi truy vấn Teradata/Qdrant kèm mỗi response (header x-ol-queries)
```

## API

| Method     | URL                     | Mô tả                                                          |
|------------|-------------------------|----------------------------------------------------------------|
| GET        | `/api/users`            | danh sách người dùng                                           |
| GET/PUT    | `/api/profile`          | hồ sơ người dùng hiện tại + điểm yêu thích từng cụm            |
| POST       | `/api/recommend`        | `{context, exclude?, members?, limit?}` → `Recommendation[]`   |
| GET/POST   | `/api/meals`            | bữa ăn của người dùng hiện tại / thêm bữa                      |
| PUT/DELETE | `/api/meals/:id`        | sửa / xoá bữa ăn                                               |
| GET/POST   | `/api/dishes`           | danh sách / thêm món                                           |
| PUT/DELETE | `/api/dishes/:itemId`   | sửa / xoá món                                                  |
| GET        | `/api/clusters`         | `{clusters, dishes}`                                           |
| GET        | `/api/stats`            | số liệu cho trang Thống kê                                     |
| GET        | `/api/evaluation`       | số liệu cho trang Đánh giá mô hình                             |
| GET        | `/api/weather?city=hcm` | thời tiết hiện tại (Open-Meteo), `hcm` / `hn` / `dn`           |

Khi làm backend, thay các hàm trong `src/lib/store.ts` và `src/lib/evaluation.ts` bằng truy vấn Teradata/Qdrant
và kết quả chạy thật. Route và UI giữ nguyên.

## Docker Compose từ thư mục gốc repo

```bash
cd ..
docker compose up -d --build office-lunch
```

Mở http://localhost:3000. Xem [README gốc](../README.md) để cấu hình cổng,
kiểm tra kết nối Teradata sandbox và chạy Qdrant tùy chọn.
`/api/health` báo trạng thái web cùng `dataMode: mock`; không kiểm tra database.
