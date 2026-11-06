# OfficeLunch trên AI Dubbing sandbox

Ứng dụng chạy native dưới Supervisor tại `/Users/gper/Workplace/dubbing/dbms`.
Database dùng Qdrant/Teradata hiện có; cấu hình này không tạo hoặc bật VM.

- FE: cổng riêng `18300`, bind `0.0.0.0` (localhost và IP máy sandbox).
- API: `http://127.0.0.1:8002` trên sandbox, FE proxy cùng origin.
- Credentials: `.env` có sẵn trong checkout sandbox; không ghi đè khi deploy.
- Python: `backend/.venv`, Python 3.11; Node: `v22.23.3` hiện có trên sandbox.
- Artifact: `/Users/gper/Workplace/dubbing/office-lunch-lab/backend/artifacts`.
  Override bằng `OFFICE_LUNCH_ARTIFACT_DIR` nếu chuyển vị trí artifact.
- Log: `/Users/gper/Workplace/dubbing/.runtime/logs/office-lunch-*.log`.

Nếu cổng 18300 không truy cập được từ client nhưng SSH vẫn thông, dùng tunnel:

```bash
# Chạy trên máy local và giữ terminal mở
ssh -p 22111 -N -L 127.0.0.1:13002:127.0.0.1:18300 gper@100.65.210.21
```

Mở `http://127.0.0.1:13002`. Cách này đã kiểm tra cả trang FE, JS/CSS và proxy
API; không cần thay đổi firewall hoặc dịch vụ khác. Logon SQL vẫn cần Teradata
sẵn sàng dù giao diện truy cập được qua tunnel.

## Cloudflare origin

Nếu `cloudflared` chạy trực tiếp trên sandbox, chọn service **HTTP**, URL
`http://127.0.0.1:18300`. Chỉ trỏ frontend; `/api/*` đã proxy tới
`127.0.0.1:8002`, không cần tạo hostname/tunnel riêng cho API.
Nếu `cloudflared` chạy trong Docker trên cùng sandbox, dùng
`http://host.docker.internal:18300` thay cho loopback của container.

Cổng 3002 đã được thay bằng 18300 ngày 06-11; cấu hình Cloudflare/domain do
người dùng thực hiện. Trang FE và proxy readiness đã được kiểm HTTP 200 cả khi
gửi Host header tùy chỉnh.

## Build

Kiểm tra branch main, origin, worktree và cổng trước khi pull. Dừng riêng các
process OfficeLunch đang chạy trước khi build lại; ghi nhận process đã dừng từ
trước để giữ nguyên trạng thái đó. Không chạy update/start/restart toàn sandbox.

```bash
cd /Users/gper/Workplace/dubbing/dbms
git pull --ff-only origin main
# Chỉ tạo venv nếu chưa có; dùng Python 3.11 sẵn có.
/Users/gper/.local/bin/uv venv --python 3.11 backend/.venv
/Users/gper/.local/bin/uv pip install --python backend/.venv/bin/python -r backend/requirements.txt
PYTHONPATH="$PWD/backend" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  backend/.venv/bin/python -m pytest backend/tests -q

export PATH=/Users/gper/.nvm/versions/node/v22.23.3/bin:$PATH
export npm_config_cache="$PWD/.runtime/npm-cache"
cd office-lunch
npm ci
BACKEND_URL=http://127.0.0.1:8002 NEXT_TELEMETRY_DISABLED=1 npm run build
mkdir -p .next/standalone/.next
cp -R .next/static .next/standalone/.next/
cp -R public .next/standalone/
```

Proxy endpoint được cố định lúc build. Standalone cần cả `.next/static` và
`public`; `run-service.sh frontend` chạy `server.js` bằng Node native.

## Supervisor

Thêm đường dẫn file `office-lunch.conf` vào `[include]` của cấu hình Supervisor
hiện có, giữ nguyên các định nghĩa dịch vụ khác. Không tạo Supervisor thứ hai.

```ini
[include]
files=/Users/gper/Workplace/dubbing/dbms/deploy/sandbox/office-lunch.conf
```

```bash
cd /Users/gper/Workplace/dubbing
./control.sh reread
./control.sh update office-lunch
./control.sh status 'office-lunch:*'
```

Sau khi dựng lại database và nghiệm thu, cả API/frontend/worker đều autostart.
Chỉ bật worker khi Teradata logon được và model/collection đã activate nhất quán.
Khi triển khai lần đầu chưa có model/database, đặt riêng worker `autostart=false`.
Dùng một worker
cho namespace `officelunch`; dừng worker local nếu có trước khi chuyển sang đây.

```bash
./control.sh start office-lunch:office-lunch-worker
# Restart đúng process khi cần, không restart sibling:
./control.sh restart office-lunch:office-lunch-api
./control.sh restart office-lunch:office-lunch-frontend
```

## Kiểm chứng

```bash
curl --fail http://127.0.0.1:8002/api/health/live
curl --fail http://127.0.0.1:8002/api/health/ready
curl --fail http://100.65.210.21:18300/api/health/live
```

HTTP 200 trang FE/liveness chỉ xác nhận process và proxy. Readiness 503 nghĩa là
DB hoặc model chưa sẵn sàng; CRUD/recommend chưa được nghiệm thu khi SQL không
logon được. Không gọi migration/import/activate để vượt qua sự cố WAL khi chưa
có phương án phục hồi được cho phép. Xem [sự cố Teradata](../../Docs/Incident-2026-11-02.md)
và [kết quả kiểm chứng](../../Docs/Results.md).

Sau dựng lại ngày 06-11, SQL/model/Qdrant đều ready. Xem
[biên bản nghiệm thu](../../Docs/Teradata-Rebuild-2026-11-06.md).
VM Teradata vẫn khởi động thủ công sau reboot host; không dùng autostart của
worker để kết luận VM đã sẵn sàng.

Kiểm tra worker đang chạy, tạo rồi dọn riêng dữ liệu thử:

```bash
cd /Users/gper/Workplace/dubbing/dbms
API_URL=http://100.65.210.21:18300 /bin/bash deploy/sandbox/run-service.sh python tests/live_worker.py
```

Đối chiếu persistence khi bảo trì VM: dừng API/worker, chạy
`python tests/verify_database_restart.py before` qua wrapper, shutdown guest
sạch rồi bật lại; sau khi DBS 5, chạy phase `after` trước khi mở traffic.
Script chỉ đọc SQL và ghi fingerprint vào artifact root, không tự restart VM.
