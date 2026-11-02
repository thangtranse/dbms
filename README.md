# OfficeLunch — Teradata + Qdrant

Ứng dụng gợi ý bữa trưa, CRUD và thống kê dùng **Teradata thật**, tìm kiếm vector
bằng **Qdrant thật**. FE Next.js → `/api/*` proxy → FastAPI Python. Không còn API
mock trong FE. Database dùng sandbox `100.65.210.21`, không tạo VM Teradata local.

## Khởi chạy local

Yêu cầu Docker Compose v2 và quyền truy cập Tailscale sandbox.

```bash
cp .env.example .env # chỉ khi chưa có .env
# Điền TERADATA_USER, TERADATA_PASSWORD, QDRANT_API_KEY từ sandbox qua kênh riêng.
docker compose build api office-lunch
docker compose run --rm api python -m ol.cli migrate
docker compose run --rm api python -m ol.cli import-food
docker compose up -d api office-lunch vector-worker
```

- [Ứng dụng](http://localhost:3000), cổng tùy chỉnh `OFFICE_LUNCH_PORT`.
- [OpenAPI/Swagger](http://127.0.0.1:8001/docs), cổng `OFFICE_LUNCH_API_PORT`.
- Liveness: `curl --fail http://127.0.0.1:8001/api/health/live`.
- Readiness SQL/Qdrant/model: `curl --fail http://127.0.0.1:8001/api/health/ready`.
- Log: `docker compose logs -f api vector-worker`.
- Dừng riêng app: `docker compose stop office-lunch api vector-worker`.

Import là idempotent theo checksum food. Migration chỉ tạo schema `officelunch`
và các bảng của ứng dụng; cần tài khoản sandbox có quyền tạo database hoặc DBA
chuẩn bị schema này trước. Không chạy migration với tên database tùy ý.

CRUD/thống kê chạy được trước khi có model. Gợi ý cần artifact đã train,
activate và copy từ sandbox về `backend/artifacts` theo
[hướng dẫn backend](backend/README.md). Worker không tự huấn luyện hoặc tạo vector
giả. Dữ liệu đã ghi SQL có thể hiển thị `vector pending` trong lúc Qdrant đồng bộ.

## Huấn luyện và benchmark

Chạy CLI trên sandbox gần hai database; không chạy qua HTTP request.
Xem [backend/README](backend/README.md) để chuẩn bị native Python 3.11, chạy
Trans2Vec 10 seed, activate, sync và benchmark. Kết quả hoàn tất hiển thị ở
[màn hình đánh giá](http://localhost:3000/evaluation).

Benchmark so cùng vector/corpus/query giữa Teradata SQL exact, Qdrant exact và
Qdrant ANN; đo cả tốc độ lẫn recall/chất lượng yes/no. Không dùng tên món hoặc
metadata demo để đánh giá mô hình trên food. Đọc [phương pháp và giới hạn](Docs/Benchmark.md)
trước khi diễn giải kết quả: dataset nhỏ, Teradata VM và Qdrant container có
cấu hình tài nguyên khác nhau.

## FE development và kiểm thử

```bash
cd office-lunch
npm ci
BACKEND_URL=http://127.0.0.1:8001 npm run dev -- --hostname 127.0.0.1
npm run lint
npm run build
```

Proxy destination được cấu hình khi Next.js build; đổi backend endpoint cần
build lại FE. Compose dùng hostname `api:8000` trong network nội bộ.

```bash
docker compose run --rm api python -m pytest tests -q
docker compose run --rm -e LIVE_DB_TESTS=1 api python -m pytest tests -q
```

`LIVE_DB_TESTS` chỉ ghi fixture vào schema riêng rồi rollback. Credentials và
artifact/model lớn được gitignore. FE/API bind localhost, chưa có đăng nhập;
`x-user-id` chỉ là bộ chọn user demo. Dependency Next.js 15.5.4 hiện có cảnh báo
bảo mật; cần nâng cấp trước khi công khai qua Internet.

## Database và tài liệu

- Teradata sandbox: `100.65.210.21:1025`; client kiểm tra `SELECT 1`:
  `docker compose --profile teradata run --rm teradata-client python /app/healthcheck.py`.
- Qdrant sandbox: REST `http://100.65.210.21:6333`, gRPC `:6334`.
- Qdrant local chỉ bật khi chủ động dùng profile:
  `docker compose --profile local-qdrant up -d qdrant`. API mặc định vẫn dùng
  sandbox; muốn chuyển cần đổi `QDRANT_URL` và key tương ứng.
- Không chạy script tạo/start VM Teradata ở local. Không dùng `down -v` để tránh
  xóa volume Qdrant local.

Xem [kết quả và trạng thái nghiệm thu](Docs/Results.md), [Docs](Docs/README.md), [API](Docs/API.md),
[backend](backend/README.md), [FE](office-lunch/README.md).

[Lịch sử triển khai](Docs/History.md) ghi lại các thay đổi và kiểm chứng;
[vận hành/phục hồi](Docs/Operations.md) hướng dẫn xử lý sandbox reboot và đổi model.
