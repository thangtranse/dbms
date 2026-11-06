# Vận hành và phục hồi OfficeLunch

## Kiểm tra từ máy local

```bash
ssh -o ConnectTimeout=8 -p 22111 gper@100.65.210.21 hostname
docker compose ps
curl --fail http://127.0.0.1:8001/api/health/live
curl --fail http://127.0.0.1:8001/api/health/ready
docker compose logs --tail 100 api vector-worker
```

`live` chỉ kiểm tra API process. `ready` cần Teradata, model load được và hai
collection Qdrant của active model. Container healthy không chứng minh toàn bộ
luồng recommend đang hoạt động.

API Compose bind IPv4 loopback. Dùng `127.0.0.1:8001` để tránh `localhost` phân
giải sang IPv6 và truy cập nhầm một dịch vụ khác trên máy. Không dừng dịch vụ
khác chỉ để xử lý xung đột này. Logon timeout không phải deadline toàn request;
readiness còn kiểm tra model/Qdrant sau SQL, nên có thể mất lâu hơn 10 giây.

## Sau khi sandbox reboot

1. Xác nhận Tailscale/SSH đã thông; kiểm tra Qdrant cổng 6333, dung lượng và VM.
2. Kiểm tra VM từ checkout **trên sandbox**, không chạy launcher ở máy local:

   ```bash
   cd /Users/gper/Workplace/dubbing/dbms
   ./teradata/bin/status-vantage.sh
   ```

3. Nếu VM đang tắt, chỉ bật VM hiện có khi được người vận hành cho phép:

   ```bash
   ./teradata/bin/start-vantage.sh
   ```

   Giữ nguyên ba overlay trong `teradata/runtime/vantage-express/overlays`.
   Không xóa/recreate ổ đĩa, không reset schema, không restart VM đang chạy.
   Cổng 1025 mở chưa đủ: đợi `SELECT 1` thực thi thành công.
4. Restart riêng API nếu pool còn kết nối SQL cũ sau reboot, rồi kiểm tra ready:

   ```bash
   docker compose up -d --force-recreate api
   ```

5. Nếu model chưa đổi, bật lại worker và kiểm tra pending/retry; không train lại
   chỉ vì HTTP request lỗi. Nếu train bị ngắt, thư mục không có manifest complete
   không được activate. Chạy run ID mới và giữ artifact cũ để kiểm tra nguyên nhân.

## Đổi active model

Dừng API và worker ở cả nơi đang phục vụ local/sandbox trước khi activate.
Không nhận ghi ứng dụng trong khoảng đổi model, và không chạy worker ở hai máy
cùng lúc. Worker chính hiện chạy native trên sandbox.

```bash
# Local
docker compose stop api vector-worker
# Trên sandbox, dừng đúng process OfficeLunch:
cd /Users/gper/Workplace/dubbing
./control.sh stop office-lunch:office-lunch-api office-lunch:office-lunch-worker
# Sandbox, trong thư mục lab
cd /Users/gper/Workplace/dubbing/office-lunch-lab
backend/run-sandbox.sh activate --run-id <completed-model-run> --seed 0
backend/run-sandbox.sh sync --drain
```

Copy thư mục seed cần dùng, manifest và **sau cùng** `active.json` về local.
Active pointer phải trỏ đến model đã có đầy đủ file local. Các collection cũ
được giữ nguyên; không xóa để xử lý lỗi trong thời gian bàn giao.

```bash
# Local, sau khi copy xong
docker compose up -d api office-lunch
curl --fail http://127.0.0.1:8001/api/health/ready
# Trên sandbox, sau khi kiểm tra CRUD/outbox:
cd /Users/gper/Workplace/dubbing
./control.sh start office-lunch:office-lunch-api office-lunch:office-lunch-worker
```

`sync --drain` dừng khi không còn event đồng bộ được trong lượt xử lý. Item mới
chưa có vector vẫn pending; đây không phải lý do tạo vector ngẫu nhiên hoặc
huấn luyện trong request. Dữ liệu đã commit trong SQL vẫn tồn tại khi Qdrant lỗi.

## Publish lại kết quả mà không chạy lại thực nghiệm

```bash
# Sandbox lab
backend/run-sandbox.sh publish --run-id <completed-run>
```

Lệnh đọc manifest complete, kiểm checksum dataset và upsert kết quả vào schema
ứng dụng. Giữ nguyên manifest/raw JSONL; bổ sung diễn giải qua `annotations.json`
nếu cần. Xem [hướng dẫn backend](../backend/README.md) và [History](History.md).
