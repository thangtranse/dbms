# Teradata + Qdrant development stack

Bộ cấu hình này chạy **Qdrant thật** bằng Docker và cung cấp một container
**Teradata client/toolbox** để kết nối tới Teradata Vantage bên ngoài.

> Teradata không phát hành database server dưới dạng Docker image chính thức.
> Vantage Express được Teradata phân phối dưới dạng máy ảo; vì vậy service
> `teradata-client` không phải database server và cần một Vantage endpoint có sẵn.

## OfficeLunch FE

Ứng dụng Next.js nằm trong `office-lunch/`. Hiện API nội bộ dùng dữ liệu giả trong
bộ nhớ; thay đổi bị mất khi restart và không được chia sẻ đáng tin cậy giữa nhiều
process. FE chưa đọc/ghi Teradata hoặc Qdrant. Thời tiết gọi Open-Meteo.

```bash
cp .env.example .env  # chỉ thực hiện nếu chưa có .env
# Điền credentials sandbox vào .env; không commit file này.
docker compose up -d --build office-lunch
docker compose ps office-lunch
curl --fail http://localhost:3000/api/health
```

Mở [OfficeLunch](http://localhost:3000). Đổi `OFFICE_LUNCH_PORT` nếu cổng 3000
đã dùng. Health trả `dataMode: mock`, chỉ kiểm tra web server.
Build cần Internet để tải npm packages và font Google. Container chạy bằng user
`node`, dùng output standalone; cổng web chỉ bind localhost.

Chạy dev (Node.js 22, npm):

```bash
cd office-lunch
npm ci
npm run dev -- --hostname 127.0.0.1
# Kiểm tra source:
npm run lint
npm run build
```

Phiên bản dependency hiện tại có cảnh báo bảo mật từ `npm ci` (bao gồm Next.js
15.5.4). Bản chạy này bind localhost; cần nâng dependency và kiểm tra lại trước
khi triển khai cho người dùng qua Internet.

Dừng riêng FE: `docker compose stop office-lunch`.
Xem log: `docker compose logs -f office-lunch`.

## Kết nối Teradata sandbox có sẵn

Teradata Vantage Express đang ở `100.65.210.21:1025` qua Tailscale. Không chạy
script tạo/start VM trên máy local. `.env.example` đã đặt host này; điền user và
password từ cấu hình sandbox qua kênh riêng. Máy chạy Docker cần truy cập được
Tailscale sandbox.

```bash
docker compose --profile teradata run --rm teradata-client python /app/healthcheck.py
```

Thành công: `Teradata connection is healthy` (`SELECT 1`). Đây là kiểm tra client
kết nối database, chưa phải tích hợp các API nghiệp vụ OfficeLunch.

## Qdrant

Sandbox đã có Qdrant tại `100.65.210.21:6333` (REST) và `:6334` (gRPC).
API key nằm trong `.env` sandbox tại `/Users/gper/Workplace/dubbing/dbms`.
Không đưa credentials vào biến `NEXT_PUBLIC_*`.

Nếu muốn chạy Qdrant riêng tại local:

```bash
docker compose up -d qdrant
```

Dashboard: [localhost:6333/dashboard](http://localhost:6333/dashboard).
Dữ liệu lưu trong volume `dbms_qdrant_data`.

## Compose và tài liệu

- `docker compose up -d --build office-lunch`: chỉ FE, dùng dữ liệu mẫu.
- `make up`: FE và Qdrant local.
- `make up-all`: FE, Qdrant local và client kết nối Teradata sandbox.
- `docker compose --profile teradata ps`: trạng thái các service.
- `docker compose --profile teradata down`: dừng container, giữ volume.

Không dùng `down -v` nếu cần giữ dữ liệu Qdrant.
Xem [Docs](Docs/README.md), [Teradata](Docs/Teradata.md), [Qdrant](Docs/Qdrant.md)
và [chi tiết FE/API](office-lunch/README.md).
