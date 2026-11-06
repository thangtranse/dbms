# Kết quả kiểm chứng OfficeLunch — cập nhật 2026-11-06

## Trạng thái hiện tại sau dựng lại Teradata

Theo ủy quyền bỏ dữ liệu cũ, Teradata đã được dựng lại trên sandbox từ VMDK gốc.
Model `food-trans2vec-v4-s0` đã activate; vector đã đồng bộ, benchmark artifact
đã publish lại kèm cảnh báo legacy. Readiness local và sandbox đều HTTP 200 với
SQL/model/Qdrant true. API/FE/worker native đều RUNNING; outbox không còn pending.

16 tests có SQL thật qua; CRUD/ownership/conflict/partial update qua; ca Qdrant
lỗi/retry revision mới và worker thường trực upsert/delete tự động đều qua.
Bộ lọc qua FE: 18 context, 40 gợi ý. Màn hình evaluation hiển thị đúng model v4,
30 dòng benchmark lịch sử và cảnh báo về vector v2.

Sau tắt/mở VM sạch, fingerprint nội dung cả 12 bảng khớp hoàn toàn. Có snapshot
khỏe offline đã kiểm checksum. Xem [biên bản dựng lại](Teradata-Rebuild-2026-11-06.md)
cho đường dẫn backup, số lượng và giới hạn phục hồi dữ liệu cũ.

## Model v4 đã hoàn tất và activate

Run `food-trans2vec-v4`: 10 seed 0–9, 128 chiều, 50 epoch, minsup 0.006,
Gensim 4.3.3 / NumPy 1.26.4. Chạy native trên sandbox trong 678,69 giây.
Mỗi seed có train 3.200 và test 800; itemset chỉ khai phá từ train. Audit native
đã qua: checksum food, nhóm giao dịch không giao giữa train/test, float32 finite
và chuẩn hóa, nhãn khớp ID, support itemset đủ ngưỡng trên train, confusion matrix
đủ 800 mẫu. Audit lại trên Docker Linux ARM cũng qua, gồm load đủ ba model của
mỗi seed (30 file). `validation.json` và toàn bộ model/split/vector đã sao lưu
local; bản audit native lưu riêng `validation-native.json`.

| Phương pháp + LinearSVC | Accuracy trung bình | Macro-F1 trung bình |
|---|---:|---:|
| Bag-of-items | 62,11% | 0,6210 |
| Trans2Vec-Ind | 42,84% | 0,3110 |
| Trans2Vec-Joi | 38,30% | 0,3477 |

Đây là số thực từ 10 seed, không phải số liệu tái lập bài báo. Trong cấu hình
hiện tại baseline tốt hơn hai biểu diễn Doc2Vec; không suy ra Trans2Vec giúp
tăng chất lượng dự đoán trên food. Việc khắc phục numerical regression không
đồng nghĩa chất lượng mô hình đã tốt. Cần nghiên cứu cấu hình/khả năng tổng quát
hóa riêng nếu muốn cải thiện; không dùng test để chọn tham số của run đã báo cáo.

Run v3 bị ngắt ở seed 9 sau reboot, không có manifest complete nên không dùng.
V4 được activate/publish ngày 06-11 sau khi dựng lại SQL; active pointer local
và sandbox cùng trỏ đến model này. Đánh giá mô hình không được tính lại khi publish.

## Benchmark database đã hoàn tất

Run: `food-bench-v4`; training artifact: `food-trans2vec-v2`, seed 0. Corpus 3200, test 800, k=15; 5 lượt × concurrency 1/4 × 3 engine = 24.000 query đo, ngoài warmup.

Các số dưới là trung bình của 5 thống kê theo lượt, không phải percentile gộp.

| CC | Engine | P50 ms TB | P95 ms TB | P99 ms TB | QPS TB | Recall@15 TB | Lỗi |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | teradata_exact | 757.263 | 1018.727 | 1158.098 | 1.32 | 1.00000 | 0 |
| 1 | qdrant_exact | 2.702 | 3.756 | 5.059 | 330.19 | 1.00000 | 0 |
| 1 | qdrant_ann | 2.723 | 3.208 | 4.060 | 347.54 | 0.98300 | 0 |
| 4 | teradata_exact | 1787.455 | 2676.153 | 3584.242 | 2.16 | 1.00000 | 0 |
| 4 | qdrant_exact | 6.393 | 8.529 | 9.912 | 608.21 | 1.00000 | 0 |
| 4 | qdrant_ann | 6.582 | 8.832 | 10.140 | 586.23 | 0.98300 | 0 |

Teradata SQL exact dùng biểu diễn theo từng chiều và join/aggregate; Qdrant dùng
vector index chuyên dụng. Teradata trong VM và Qdrant trong Docker có cấu hình
khác nhau. Đây là so sánh hai triển khai trên sandbox, không phải xếp hạng tổng
quát hai CSDL. Trên tập nhỏ này ANN không thể hiện lợi thế rõ so với exact.

**Giới hạn artifact:** vector v2 được sinh trước khi phát hiện lỗi Gensim 4.4.0
[#3665](https://github.com/piskvorky/gensim/issues/3665). Độ đúng retrieval được
đối chiếu trực tiếp với NumPy trên chính các vector cố định này. Không sử dụng
Accuracy/F1 của run legacy để kết luận chất lượng Trans2Vec sau khi sửa runtime.

Dataset SHA-256: `7fb90d30802632fc9dbabe737db099b1f4b155fc81e98cc3b4cb1fd5fb7bdd7d`.

Manifest và 30 file JSONL: `backend/artifacts/food-bench-v4/` (gitignored).
Kết quả API: `/api/benchmarks/food-bench-v4`.

Xem [phương pháp và giới hạn](Benchmark.md) và [vận hành](../backend/README.md).

## Trạng thái lịch sử ngày 2026-11-02 (đã được thay thế bởi cập nhật 06-11)

- Build FE, Compose validation và kiểm tra source đã qua.
- Bộ dependency thay thế đã qua 16 tests cả trên sandbox và Docker local ở
  ngày trước, khi chạy live tests tuần tự. Đây không phải bằng chứng SQL hiện tại
  healthy sau reboot.
- Kiểm tra offline ngày 02-11: 13 passed, 3 live tests skipped. Lần thử live
  không qua do DBS không nhận logon; đã dừng thử lại khi tìm thấy lỗi WAL.
- Tailscale/SSH đã thông, Qdrant `/healthz` HTTP 200 từ host và container API;
  các collection legacy còn tồn tại.
- VM hiện có đã được bật lại sau khi người dùng cho phép. `pdestate` báo
  `RUN/READY`, DBS `0/-1`; log có WAL error 5192 và crash limit 13857.
  Xem [biên bản sự cố](Incident-2026-11-02.md).
- FE/API process được bật; FE HTTP 200. Readiness hiện trả HTTP 503:
  `teradata=false`, `model=false`, `qdrant=true` (quan sát 30,12 giây).
  Model legacy v2 không load trong runtime NumPy 1.26.4 mới; chưa đổi pointer
  sang v4 vì phải activate SQL/Qdrant nhất quán trước.
- Còn phải sau khi Teradata phục hồi: đối chiếu dữ liệu/import, activate v4,
  sync, publish v4/annotations benchmark, chạy `live_smoke.py`,
  `live_filters.py`, `live_outbox.py`, bật vector-worker và xác nhận readiness/UI.
- Worker vẫn dừng. Không reset WAL/crash counter hoặc tạo lại database để
  vượt kiểm thử; chưa có xác nhận dữ liệu SQL còn nguyên sau reboot.

Không dùng trạng thái liveness của container để kết luận database đang truy cập được.
Không tạo database server local để thay sandbox trong thời gian gián đoạn.
