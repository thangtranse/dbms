# Giới thiệu Teradata

Teradata Vantage là nền tảng cơ sở dữ liệu SQL phục vụ phân tích dữ liệu.
Kiến trúc MPP chia công việc cho nhiều bộ xử lý để thực hiện song song.
Parsing Engine phân tích và lập kế hoạch truy vấn; BYNET truyền dữ liệu giữa các
thành phần; AMP xử lý dữ liệu, join và tổng hợp trên phần dữ liệu được giao.
Primary Index thường quyết định cách phân phối hàng bằng hàm băm; lựa chọn khóa
không phù hợp có thể làm dữ liệu lệch về một số AMP. Primary Index có vai trò
phân phối dữ liệu, khác với ràng buộc Primary Key của mô hình quan hệ.

## Trong project

Dự kiến lưu dữ liệu có cấu trúc: người dùng, món ăn, bữa ăn và chi tiết bữa ăn.
SQL phù hợp cho CRUD, join và thống kê chi phí/lịch sử theo thời gian.
Hiện các API OfficeLunch vẫn thao tác kho dữ liệu giả trong bộ nhớ.

## Sandbox hiện có

- Host Tailscale: `100.65.210.21`, SQL TCP `1025`.
- Vantage Express chạy bằng QEMU trên Intel macOS; không tạo lại VM tại máy local.
- Repo sandbox: `/Users/gper/Workplace/dubbing/dbms`.
- `teradata-client` trong Compose là Python client, không phải database server.
- Tài khoản lấy từ `.env` sandbox, không đưa mật khẩu vào Git hoặc biến `NEXT_PUBLIC_*`.

Máy local cần tham gia Tailscale và có quyền truy cập sandbox. Sau khi điền `.env`:

```bash
docker compose --profile teradata run --rm teradata-client python /app/healthcheck.py
```

Lệnh chỉ chạy `SELECT 1`, không tạo schema hay ghi dữ liệu. Nếu sandbox không
truy cập được, kiểm tra Tailscale và trạng thái VM trước khi cân nhắc restart.

## Nguồn chính thức

- [Kiến trúc Vantage](https://github.com/Teradata/quickstarts/blob/main/modules/ROOT/pages/teradata-vantage-engine-architecture-and-concepts.adoc)
- [Teradata SQL Driver for Python](https://github.com/Teradata/python-driver)
