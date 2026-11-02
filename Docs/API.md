# API OfficeLunch

Base URL qua FE: `/api`. Swagger trực tiếp: `http://127.0.0.1:8001/docs`.
`x-user-id`: chọn một user demo; bỏ trống dùng `u-001`; ID không tồn tại trả 404.
Đây là chức năng demo không có authentication, không dùng header này làm quyền
truy cập trong sản phẩm công khai.

- `GET /users`: danh sách user.
- `GET /profile`: `{profile, affinity}`; `PUT /profile`: patch các trường khẩu vị.
- `GET/POST /dishes`, `PUT/DELETE /dishes/{itemId}`: món lưu Teradata.
  Body ghi: `itemId,name,price,categoryId,tags,image`. ID không đổi khi sửa.
- `GET/POST /meals`, `PUT/DELETE /meals/{id}`: lịch sử theo user.
  POST: `date,itemIds,label,context?`; PUT cho phép patch, kể cả chỉ đổi `label`.
- `GET /stats`: thống kê SQL thật, không cộng nghiên cứu food vào lịch sử demo.
- `GET /clusters`: `{clusters,categories,dishes}`. Category do người dùng gán,
  cluster tính bằng KMeans; `clusterId=-1` khi chưa có embedding.
- `POST /recommend`: `{context,exclude?,members?,limit?}`. Cosine trả số thực,
  không phải xác suất thích; cold start trả `score:null`, xếp theo phổ biến.
  GroupSize là metadata ngữ cảnh; members mới xác định những hồ sơ cần kết hợp.
- `GET /evaluation`: kết quả huấn luyện đã publish, hoặc `{status:"not_run",results:[]}`.
- `GET /benchmarks`, `GET /benchmarks/{runId}`: summary benchmark đã hoàn tất.
- `GET /weather?city=hcm|hn|dn`: Open-Meteo; response ghi rõ fallback khi lỗi.
- `GET /health/live`, `GET /health/ready`: process và dependencies/model.

400 cho input sai, 404 cho không tồn tại/không thuộc user, 409 khi trùng ID hoặc
xóa món đang có lịch sử, 503 khi dependency/model không sẵn sàng. DELETE thành
công trả 204. Món và bữa ăn có `vectorStatus:pending|synced`; sửa SQL thành công
không có nghĩa Qdrant đã nhận bản mới.

`x-ol-queries`: URI-encoded JSON, tối đa 6 KB; SQL template không kèm bind values,
truy vấn Qdrant không kèm API key; `durationMs` và `rows` là quan sát thực tế.
Header chỉ chứa các entry vừa giới hạn được, không phải audit log đầy đủ.
