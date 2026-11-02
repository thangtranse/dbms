# Lịch sử triển khai OfficeLunch

Các mốc dưới đây ghi lại công việc đã thực hiện và bằng chứng kiểm tra. Ngày
theo múi giờ Việt Nam. Artifact lớn và secrets không đưa vào Git; tài liệu này
không thay thế manifest hoặc số đo thô.

## 2026-11-01 — Backend và tích hợp dữ liệu thật

- Chọn Python 3.11 + FastAPI cho API, pipeline và CLI benchmark. FE Next.js
  chuyển `/api/*` sang API; loại bỏ route/store/mock result cũ trong FE.
- Tạo schema ứng dụng `officelunch` trên Teradata sandbox, import đủ 4.000
  giao dịch food, giữ ID theo dòng và checksum. Import chạy lại không nhân đôi.
- Giữ snapshot demo gồm người dùng, tên món, giá, tag và lịch sử; đánh dấu
  synthetic. Item chưa có mapping hiển thị `Item #ID`. Tách `categoryId`
  thủ công khỏi `clusterId` do KMeans tính từ vector.
- Triển khai CRUD, khẩu vị, lịch sử, thống kê SQL; ghi entity và outbox trong
  cùng transaction. Qdrant dùng collection có phiên bản, worker retry và chỉ
  xác nhận revision đã đồng bộ.
- Thêm pipeline train-only FP-growth/Doc2Vec cho Trans2Vec-Ind/Joi, baseline
  Bag-of-items + LinearSVC, split theo nhóm giao dịch trùng và 10 seed cố định.
- Triển khai benchmark Teradata SQL exact, Qdrant exact và HNSW ANN, cùng
  corpus/query float32 và kNN15; oracle NumPy float64, recall có xử lý hòa điểm.
- Hoàn tất `food-bench-v4`: 24.000 truy vấn đo, 30 nhóm kết quả, không có lỗi.
  Vector lấy từ `food-trans2vec-v2`, seed 0. Xem [Results](Results.md) để biết
  số đo, cấu hình và giới hạn của artifact legacy này.
- Phát hiện numerical regression của Gensim 4.4.0 liên quan dot product -1;
  pin Gensim 4.3.3 / NumPy 1.26.4 / SciPy 1.13.1 và thêm gate trước train/load.
  Không diễn giải Accuracy/F1 v2 như kết quả của runtime đã sửa.
- Bộ 16 tests qua trên native sandbox và Docker khi chạy tuần tự; có kiểm tra
  rollback Teradata, SQL cosine và fixture pipeline. Kiểm tra CRUD qua FE
  xác minh ownership, partial update, conflict và pending vector.
- Build FE/API và Compose validation qua. Bổ sung Docs API, Benchmark,
  Teradata/Qdrant, README và hướng dẫn vận hành.
- Kết nối sandbox bị gián đoạn trong lúc train `food-trans2vec-v3`. Chưa bật
  worker thường trực hoặc kết luận hoàn tất nghiệm thu ở thời điểm đó.

## 2026-11-02 — Khôi phục sau reboot và hoàn tất bàn giao

- SSH sandbox thông trở lại. Kiểm tra còn khoảng 370 GiB trống; máy vừa reboot.
  Qdrant đã nghe cổng 6333, VM Teradata chưa chạy.
- Xác minh v3 bị ngắt ở seed 9, không có `manifest.json` complete. Giữ nguyên
  artifact v3, không ghép hoặc tự tạo kết quả cho seed còn thiếu.
- Đồng bộ source backend mới vào lab riêng
  `/Users/gper/Workplace/dubbing/office-lunch-lab`; không ghi đè checkout/.env
  sandbox và không dùng rsync `--delete`.
- Khởi chạy lượt train mới `food-trans2vec-v4` bằng native CLI, mặc định đủ
  10 seed, 128 chiều, 50 epoch, minsup 0.006.
- Sau khi người dùng cho phép bật VM hiện có, kiểm tra đủ ba overlay QCOW2 và
  chạy `teradata/bin/start-vantage.sh` **trên sandbox**. Dùng lại ổ đĩa/dữ liệu,
  không tạo VM local, không restart dịch vụ khác.
- Dừng riêng API/worker local để chuẩn bị đổi model; build lại image API/FE.
- Guest OS đã boot nhưng DBS không lên: `pdestate` báo `RUN/READY`, DBS
  `0/-1`; log ghi WAL error 5192 rồi crash limit 13857. Giữ nguyên đĩa/WAL,
  không reset hoặc khởi tạo lại. Xem [biên bản sự cố](Incident-2026-11-02.md).
- Tests offline ngày 02-11: 13 passed, 3 live skipped. Lần thử live trước đó
  không qua vì SQL chưa logon được, không dùng kết quả ngày trước làm bằng
  chứng hệ thống hiện tại healthy.
- Bổ sung `live_filters.py` để kiểm tra budget/diet/avoid/tag/exclude qua proxy
  FE; chưa chạy được vì phụ thuộc SQL. Tài liệu vận hành và lịch sử đã bổ sung.
- Giới hạn logon SQL mặc định 10 giây bằng tham số driver chính thức để API
  không giữ thread chờ logon vô hạn khi DBS không sẵn sàng; không thay timeout
  query hoặc điều kiện benchmark đã chạy trước đó.
- Bổ sung audit artifact đủ 10 seed: checksum, nhóm train/test không giao nhau,
  float32/finite/chuẩn hóa, nhãn, support itemset trên train và confusion matrix.
  Đặt `PYTHONPATH=/app` trong image để các script tích hợp chạy trực tiếp đúng
  theo lệnh README.
- `food-trans2vec-v4` hoàn tất 10 seed trong 678,69 giây; audit native qua.
  Sao lưu đủ manifest/model/split/vector về local. Baseline Accuracy TB 62,11%,
  Ind 42,84%, Joi 38,30%; ghi kết quả thật và giới hạn trong Results, không
  tuyên bố mô hình vượt baseline hoặc tái lập bài báo.
- Qdrant health HTTP 200 từ host/container, collection cũ còn tồn tại. FE/API
  process chạy nhưng readiness 503 (SQL lỗi và model legacy không tương thích
  runtime mới); không đổi active pointer trước khi activate nhất quán được.
- Người dùng xác nhận chưa có backup và yêu cầu giữ nguyên để chẩn đoán.
  Không thực hiện thao tác sửa WAL hoặc phục hồi có thể thay đổi/mất dữ liệu.
- Image Docker cuối qua 13 tests, 3 live tests bỏ qua có chủ đích. Audit đủ
  10 seed/30 model của v4 qua cả native Intel và Docker Linux ARM. Compose
  validation và `git diff --check` qua. Đồng bộ Docs vào lab sandbox để bàn giao.

Trạng thái kiểm thử và vận hành cuối cùng được ghi tại [Results](Results.md).

## Vị trí và cách đối chiếu

| Thành phần | Vị trí |
|---|---|
| Source local | `backend/`, `office-lunch/`, `compose.yaml` |
| Checkout hạ tầng sandbox hiện có | `/Users/gper/Workplace/dubbing/dbms` |
| Lab native CLI | `/Users/gper/Workplace/dubbing/office-lunch-lab` |
| Artifact sandbox | `<lab>/backend/artifacts/<runId>/` |
| Artifact local đã sao lưu | `backend/artifacts/<runId>/` (gitignored) |
| Model serving | `backend/artifacts/active.json` |
| Kết quả đã publish | Teradata `officelunch.results`, API evaluation/benchmarks |

Lịch sử này không ghi mật khẩu, API key hoặc giá trị bind có thể chứa dữ liệu
người dùng. Chưa commit/push các thay đổi trong phiên triển khai này.
