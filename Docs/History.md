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

## 2026-11-05 — Yêu cầu triển khai ứng dụng lên sandbox

- Người dùng yêu cầu deploy OfficeLunch theo skill `deploy-ai-dubbing-sandbox`:
  FE/API chạy native dưới Supervisor, dùng lại database hiện có.
- Preflight local: checkout sạch trên `main`, origin
  `git@github.com:thangtranse/dbms.git`, commit `5e5c85d7c654cda9386b692a28da8f6da23e056e`.
- Tailscale local ban đầu đang tắt; đã bật lại bằng `tailscale up` thành công.
  Sau đó target `100.65.210.21` vẫn báo offline, last seen 2 ngày, SSH 22111
  timeout khi thử lại. Chưa xác minh được checkout/Supervisor/database hiện tại.
- Chưa pull, build, cài đặt, ghi cấu hình Supervisor hoặc thay đổi process nào
  trên sandbox. Giữ yêu cầu bảo toàn dữ liệu Teradata để chẩn đoán; không suy
  diễn trạng thái lỗi ngày 02-11 là kết quả kiểm tra mới.
- Cần sandbox/Tailscale phía remote online trước khi tiếp tục preflight và deploy.

## 2026-11-06 — Deploy native FE/API thành công

- Sandbox online; preflight xác minh checkout `dbms` sạch trên main, đúng origin.
  Pull fast-forward từ `ce18dd7` lên `5e5c85d`.
- Tạo virtualenv backend riêng, cài requirements, chạy 13 tests qua/3 live tests
  skipped; npm ci và FE build/type/lint qua.
- Thêm group Supervisor `office-lunch`, API 8002 loopback và FE 3002 Tailscale.
  API/FE RUNNING, worker STOPPED. Dịch vụ khác giữ nguyên PID/trạng thái.
- Giao diện, 3 asset và liveness qua proxy được xác minh HTTP 200 qua SSH tunnel.
  Cổng frontend trực tiếp từ client timeout; hướng dẫn dùng tunnel 13002 đã thêm.
- Readiness 503: SQL/model chưa sẵn sàng; VM Teradata đang tắt, giữ nguyên yêu
  cầu bảo toàn để chẩn đoán. Chưa migrate/import/activate hoặc start worker.
- Chi tiết source, lệnh, process và bằng chứng: [Deployment-2026-11-06](Deployment-2026-11-06.md).

## 2026-11-06 — Kiểm tra/sửa Teradata theo yêu cầu tiếp theo

- VM đang tắt; đã kiểm tra QCOW2 offline và sao lưu đủ ba overlay, xác minh
  SHA-256. Bộ cài OVF/VMDK cũng khớp checksum gốc.
- Thử boot bằng lớp ghi riêng trên bản copy, giữ nguyên đĩa gốc. Guest tiếp tục
  lỗi WAL 5192 ở cả ba AMP và crash limit 13857; SQL chưa phục hồi.
- Thu thập diagnostics, yêu cầu shutdown bình thường bản thử. Không clear WAL,
  sysinit hoặc tái tạo dữ liệu; đang chờ lựa chọn bảo toàn dữ liệu/khôi phục demo.
- Chi tiết: [Teradata-Recovery-2026-11-06](Teradata-Recovery-2026-11-06.md).
- Người dùng chọn giữ dữ liệu cũ và chờ phương án DBA/Teradata Support.
  Dừng thử sửa, không tái tạo bộ đĩa/schema hoặc import lại dữ liệu.

## 2026-11-06 — Dựng lại theo ủy quyền bỏ dữ liệu hiện có

- Người dùng đổi quyết định và cho phép bỏ dữ liệu cũ để khắc phục. Giữ backup
  lỗi nhưng chuyển sang overlay mới từ nguồn đã kiểm SHA-256 trên sandbox.
- Launcher dùng writethrough, dừng riêng API trong lúc migrate/import. SQL mới
  lên RUN/STARTED, DBS 5; import 4.000 giao dịch, chạy lại không nhân đôi.
- Activate v4 seed 0; readiness cả sandbox và local HTTP 200. Bộ lọc gợi ý qua
  18 context/40 recommendation. Các kiểm chứng còn lại ghi tại
  [Teradata-Rebuild-2026-11-06](Teradata-Rebuild-2026-11-06.md).
- 16 tests gồm SQL thật qua; CRUD và outbox fault/retry qua. Snapshot khỏe tạo
  lúc guest đã tắt sạch, hash khớp; fingerprint 12 bảng khớp sau VM restart.
- API/FE/worker native RUNNING, worker tự upsert/delete qua black-box test;
  pending = 0. Readiness local/sandbox HTTP 200, browser evaluation hiển thị v4
  và benchmark lịch sử. Worker local chuyển sang profile tùy chọn để tránh trùng.

## 2026-11-06 — Đổi cổng phục vụ Cloudflare

- Theo yêu cầu tránh trùng cổng, chuyển riêng FE sandbox từ 3002 sang 18300
  (đã kiểm tra trống), bind 0.0.0.0 để dùng được localhost/IP máy sandbox.
- Chỉ restart `office-lunch:office-lunch-frontend`; API 8002 và worker giữ PID.
  FE và proxy readiness HTTP 200, kể cả khi dùng Host header tùy chỉnh.
- Cloudflare origin khi connector chạy native cùng máy:
  `http://127.0.0.1:18300`; API vẫn đi qua `/api` của FE. Chưa tạo hoặc thay đổi
  tunnel/domain Cloudflare. SSH tunnel local 13002 đã trỏ lại cổng mới.

## 2026-11-06 — Đồng bộ commit mới và thêm version build

- Người dùng xác nhận stash các thay đổi sandbox, đồng bộ, commit/push phần
  version rồi triển khai. Repo thực tế có main, không có master; upstream mới
  tại thời điểm preflight là `b3866f25885eb72e9c27a3026cf1edaa46a21963`.
- 19 file chưa commit trên sandbox đều khớp nội dung commit đó. Đã giữ nguyên
  trong stash `127a0e75b7b51010cb8aeb6a525d4aa8ef1d0bd2`, không drop/apply;
  checkout pull fast-forward từ 5e5c85d tới b3866f2.
- Bổ sung mã commit/thời điểm build trên thanh đầu FE, `/build-info`, API
  `/api/version` và liveness. Native build helper chia sẻ cùng metadata FE/API;
  Make/Compose truyền SHA cho Docker. Source chưa commit mang hậu tố dirty,
  thiếu Git/build arg báo unknown.
- Build FE/lint/type local qua; 2 Node tests version qua, backend offline
  15 passed/3 live tests skipped. Bản ghi rollout và kiểm tra sau restart được
  lưu tại `.runtime/deployments/<commit>.json` của checkout sandbox để giữ
  working tree sạch và version khớp artifact. Xem [Versioning](Versioning.md).

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
