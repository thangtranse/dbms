# OfficeLunch frontend

Next.js UI cho demo Food/Trans2Vec. API được proxy sang FastAPI; không dùng kho
mock trong bộ nhớ. Tên món/giá/người dùng là dữ liệu demo tổng hợp, không phải
mapping chính thức của mã item trong food.txt.

```bash
npm ci
BACKEND_URL=http://127.0.0.1:8001 npm run dev -- --hostname 127.0.0.1
npm run lint
npm run build
```

Backend phải chạy trước; xem [README gốc](../README.md). Docker Compose build
proxy đến `api:8000`; cấu hình proxy thay đổi cần rebuild.

| Đường dẫn | Chức năng |
| --- | --- |
| `/` | Gợi ý vector + lọc metadata demo, kNN yes/no |
| `/history` | CRUD bữa ăn và trạng thái đồng bộ |
| `/stats` | Thống kê từ SQL Teradata |
| `/dishes` | CRUD metadata món, category thủ công |
| `/profile` | Khẩu vị, món thích/kiêng theo user demo |
| `/clusters` | KMeans + PCA trên vector học được |
| `/evaluation` | Chất lượng mô hình và benchmark database thật |

“Xem truy vấn” đọc trace thực từ backend (SQL template, thời gian, số dòng),
không hiển thị bind values hoặc credentials. Thiếu kết quả thực nghiệm hiển thị
chưa chạy, không dùng số giả. Category và cluster là hai thuộc tính riêng biệt.
