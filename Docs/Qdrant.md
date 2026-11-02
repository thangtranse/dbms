# Giới thiệu Qdrant

Qdrant là cơ sở dữ liệu vector dùng để tìm các đối tượng tương tự theo biểu diễn
số của dữ liệu. Collection chứa các point; mỗi point có ID, vector và payload
(metadata JSON). Cấu hình vector quy định số chiều và thước đo khoảng cách.
Payload cho phép kết hợp tìm kiếm tương tự với lọc thuộc tính như giá hoặc nhóm món.

## Trong OfficeLunch

Pipeline Trans2Vec sinh vector món/giao dịch; ứng dụng đưa vector vào
Qdrant và truy vấn láng giềng gần để gợi ý. Teradata giữ dữ liệu quan hệ gốc,
Qdrant giữ vector và metadata phục vụ tìm kiếm. Hai bên dùng ID nghiệp vụ thống
nhất; backend cần xử lý retry, cập nhật và xóa để tránh dữ liệu không đồng bộ.

Qdrant không tự chạy Trans2Vec, phân cụm hay sinh kết quả đánh giá mô hình.
Các màn hình cụm và đánh giá đọc kết quả pipeline thực nghiệm. Chưa chạy
pipeline thì hiển thị trạng thái chưa có kết quả, không dùng số giả.

## Kết nối

- Sandbox hiện có: REST `http://100.65.210.21:6333`, gRPC `100.65.210.21:6334`.
- Local tùy chọn: `docker compose up -d qdrant`.
- Dashboard local: `http://localhost:6333/dashboard`.
- API dùng header `api-key`; không đưa key vào mã frontend hoặc Git.
- Volume local: `dbms_qdrant_data`; không xóa volume nếu cần giữ dữ liệu.

Kiểm tra sandbox qua Tailscale (key lấy từ cấu hình riêng):

```bash
curl --fail -H "api-key: $QDRANT_API_KEY" http://100.65.210.21:6333/collections
```

Lệnh liệt kê collection không chứng minh ứng dụng đã có embedding hoặc dữ liệu.

## Nguồn chính thức

- [Tổng quan](https://qdrant.tech/documentation/overview/)
- [Collection](https://qdrant.tech/documentation/manage-data/collections/)
- [Payload và lọc metadata](https://qdrant.tech/documentation/concepts/payload/)
