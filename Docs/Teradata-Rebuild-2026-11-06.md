# Dựng lại Teradata trên sandbox — 2026-11-06

Người dùng đã cho phép bỏ dữ liệu hiện có để khắc phục. Vì WAL 5192 tái diễn
trên cả ba AMP, chọn dựng bộ overlay mới từ VMDK nguồn đã kiểm chứng, không
tuyên bố cứu được dữ liệu cũ. Các thay đổi người dùng chỉ có trong database lỗi
không được phục hồi vào database mới.

## Bộ đĩa và cấu hình

- Sandbox: `100.65.210.21`, checkout `/Users/gper/Workplace/dubbing/dbms`.
- Dừng riêng API OfficeLunch trong lúc dựng lại; worker vốn đang dừng.
- Bộ lỗi được giữ tại
  `teradata/runtime/vantage-express/overlays-corrupt-20261106/`.
- Snapshot lỗi độc lập và manifest hash tiếp tục giữ trong
  `/Users/gper/Workplace/dubbing/office-lunch-lab/recovery-20261106/`.
- Overlay sạch tại đường dẫn chuẩn
  `teradata/runtime/vantage-express/overlays/`, backing vào VMDK gốc khớp SHA-256.
  Dùng đúng VM sandbox hiện có, 2 vCPU/8 GiB, SQL 1025, guest SSH 22022.
- Launcher chuyển `cache=writeback` sang `cache=writethrough`. Theo
  [tài liệu QEMU](https://www.qemu.org/docs/master/system/qemu-manpage.html),
  chế độ này flush trước khi báo hoàn thành ghi cho guest. Đây là ưu tiên độ
  bền với đánh đổi throughput ghi, không phải chứng minh nguyên nhân WAL cũ.

Không thay đổi MongoDB/Redis/MinIO, không tạo database server trên máy local.
Không cần tải lại bộ cài hoặc huấn luyện lại model.

## Import và kích hoạt

Chạy native từ checkout sandbox qua `deploy/sandbox/run-service.sh python`:

```bash
/bin/bash deploy/sandbox/run-service.sh python -m ol.cli migrate
/bin/bash deploy/sandbox/run-service.sh python -m ol.cli import-food
/bin/bash deploy/sandbox/run-service.sh python -m ol.cli import-food
/bin/bash deploy/sandbox/run-service.sh python -m ol.cli activate --run-id food-trans2vec-v4 --seed 0
/bin/bash deploy/sandbox/run-service.sh python -m ol.cli sync --drain
/bin/bash deploy/sandbox/run-service.sh python -m ol.cli publish --run-id food-bench-v4
```

SQL mới đạt `RUN/STARTED`, DBS 5 cho phép logon. Schema `officelunch` được tạo
thành công; import đủ 4.000 giao dịch, chạy lần hai báo `Food already imported`.
Checksum giữ nguyên `7fb90d30802632fc9dbabe737db099b1f4b155fc81e98cc3b4cb1fd5fb7bdd7d`.
Tên/giá/tag và lịch sử demo là snapshot synthetic, không phải ý nghĩa thật của
mã item food.

Model serving đã activate `food-trans2vec-v4-s0`. Readiness sandbox và local đã
trả HTTP 200, cả SQL/model/Qdrant true. Active pointer local được đồng bộ từ
sandbox; API local được restart để load model và bỏ kết nối SQL cũ.

## Kiểm chứng

- Native tests có SQL thật: 16 passed, gồm rollback và SQL cosine đối chiếu
  NumPy trên hai layout lưu vector.
- CRUD qua FE: tạo/sửa/xóa, duplicate 409, ownership 404, partial label update
  và trạng thái pending đã qua; dữ liệu kiểm thử được dọn.
- Outbox fault test đã qua: URL Qdrant lỗi chỉ trong process test, SQL vẫn giữ
  bữa ăn; retry áp dụng revision 2/label mới và API báo synced. Không dừng Qdrant.
- Bộ lọc qua FE proxy: 18 ngữ cảnh, 40 gợi ý; budget/diet/avoid/tag/exclude và
  query traces đều qua.
- Sau sync/drain, dừng API/worker để ghi fingerprint của cả 12 bảng. Tắt guest
  bằng `systemctl poweroff`, xác nhận QEMU thoát rồi mới copy đủ ba overlay.
- Snapshot khỏe đã được kiểm `qemu-img check` không lỗi và hash source/copy khớp:
  `/Users/gper/Workplace/dubbing/office-lunch-lab/healthy-snapshots/rebuilt-20261106/`.
  Kèm manifest, active pointer và fingerprint SQL trước restart. Giữ VMDK
  backing nguồn; snapshot QCOW2 không tự chứa toàn bộ bộ cài.
- Sau restart: PDE RUN/STARTED, DBS 5; fingerprint cả 12 bảng khớp hoàn toàn.
  `database-restart-before.json` và `database-restart-after.json` lưu tại artifact
  root trên sandbox và được sao lưu local. Không xuất hiện WAL 5192 trong lần
  boot kiểm chứng này; một lần restart sạch không bảo đảm mọi tình huống mất điện.
- API/FE/worker Supervisor đã RUNNING, worker autostart được bật sau nghiệm thu.
  Black-box test worker tự upsert/delete bữa ăn qua API và ack đúng revision 2
  đã qua, không gọi manual sync. Outbox pending = 0, 1.559 món active.
- Local API và FE proxy sandbox đều readiness HTTP 200. UI evaluation đã được
  kiểm bằng browser: model v4/10 seed, kết quả thật và 30 dòng benchmark legacy
  kèm banner cảnh báo hiển thị được.

Một worker duy nhất chạy trên sandbox. Worker Compose local đã chuyển vào
profile `local-worker`; các lệnh mặc định chỉ chạy FE/API. VM vẫn cần được bật
thủ công sau host reboot như trước; autostart app không thay thế readiness DB.

Các lệnh vận hành chỉ tác động OfficeLunch và VM Teradata. Một số process
VideosFlow/Demucs/Faster Whisper được Supervisor tự khởi động lại do exit 1;
log đã có hiện tượng này lúc 08:57–08:59 trước khi dựng VM mới (09:11).
Không ra lệnh restart hoặc sửa những service đó trong công việc này.

Số lượng trước restart: 3 user, 1.559 món active (thêm 1 tombstone test), 99 bữa
demo, 4.000 research transaction, 103.490 quan hệ research item đã dedup, 7.168
luật và 2 kết quả đã publish. Danh sách item gốc có trùng vẫn giữ trong doc food.

## Giới hạn kết quả nghiên cứu

Benchmark `food-bench-v4` là số đo lịch sử trước dựng lại, dùng vector v2 và
VM cache writeback. Publish lại chỉ nạp artifact đã hoàn tất, không có nghĩa
đã benchmark lại runtime mới hoặc vector v4. Banner cảnh báo artifact legacy
vẫn được giữ. Xem [Results](Results.md) và [Benchmark](Benchmark.md).
