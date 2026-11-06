# Triển khai native OfficeLunch — 2026-11-06

**Cổng FE hiện tại là 18300**, đã đổi từ 3002 theo yêu cầu người dùng sau các
bước dưới. Cloudflare origin native: `http://127.0.0.1:18300`. Xem
[hướng dẫn hiện hành](../deploy/sandbox/README.md); số cổng 3002 trong biên bản
phía dưới là cấu hình tại lần deploy ban đầu.

**Cập nhật sau triển khai:** đã dựng lại Teradata theo ủy quyền bỏ dữ liệu cũ;
API/FE/worker đều RUNNING, readiness HTTP 200. Model v4 đã activate và fingerprint
12 bảng qua restart khớp. Phần dưới ghi lần deploy ban đầu khi database còn lỗi;
xem [biên bản dựng lại](Teradata-Rebuild-2026-11-06.md) cho trạng thái mới.

## Kết quả

FE và API đã được triển khai lên AI Dubbing sandbox, quản lý bởi Supervisor hiện
có. Business readiness chưa đạt vì Teradata VM đang tắt và active model legacy
chưa load trong runtime mới. Worker được giữ dừng; chưa chạy CRUD/recommend hoặc
đổi model để tránh tác động dữ liệu đang chờ chẩn đoán.

| Thành phần | Trạng thái kiểm chứng |
|---|---|
| `office-lunch:office-lunch-api` | RUNNING, PID 4091 tại lần kiểm tra |
| `office-lunch:office-lunch-frontend` | RUNNING, PID 4092 tại lần kiểm tra |
| `office-lunch:office-lunch-worker` | STOPPED, autostart=false |
| FE `/`, `/evaluation` | HTTP 200 qua SSH tunnel từ máy local |
| Asset JS/CSS | 3 asset lấy từ HTML đều HTTP 200 |
| API liveness qua FE proxy | HTTP 200, `dataMode=database` |
| Readiness | HTTP 503; teradata=false, model=false, qdrant=true |
| Backend tests | 13 passed, 3 live SQL tests skipped |
| FE build | Compile, lint/type checks, static generation đều qua |

## Source và lệnh triển khai

- Checkout: `/Users/gper/Workplace/dubbing/dbms`, branch `main`, origin
  `git@github.com:thangtranse/dbms.git`; sạch trước triển khai.
- `git pull --ff-only origin main`: `ce18dd7bb7015ba549dd40d5295037c3e6f75446`
  → `5e5c85d7c654cda9386b692a28da8f6da23e056e`.
- Cấu hình bổ sung của phiên deploy: `deploy/sandbox/` và ignore `.runtime/`,
  đồng bộ từ workspace local; chưa commit/push các file bổ sung này.
- Tạo `backend/.venv` Python 3.11.17 từ interpreter sẵn có; dùng `uv pip install
  --python backend/.venv/bin/python -r backend/requirements.txt`.
- Chạy pytest offline trong venv mới; không dùng dữ liệu SQL thật để kiểm thử.
- Node sẵn có v22.23.3, `npm ci`, `BACKEND_URL=http://127.0.0.1:8002 npm run build`;
  copy public/static vào standalone output trước khi khởi chạy.
- Thêm include chỉ cho `office-lunch.conf` vào Supervisor hiện có. Bản cấu hình
  trước khi thêm được giữ tại
  `/Users/gper/Workplace/dubbing/.runtime/backups/supervisord-before-office-lunch-20261106.conf`.
- `./control.sh reread` phát hiện duy nhất group OfficeLunch mới;
  `./control.sh update office-lunch` tạo group và chạy API/FE.

Không cài system package, không thêm LaunchAgent hoặc Supervisor thứ hai.
Credentials `.env` giữ nguyên; source và runtime đều dưới deployment root.

## Truy cập và vận hành

- FE bind `100.65.210.21:3002`, API bind `127.0.0.1:8002` trên sandbox.
- Cổng 3002 kiểm tra từ máy local bị timeout; cổng 3001 cũng timeout, trong khi
  SSH 22111 và Qdrant 6333 thông. Firewall macOS báo disabled. Chưa kết luận
  nguyên nhân chính sách/đường mạng cho các cổng frontend.
- SSH tunnel đã hoạt động, cho phép mở `http://127.0.0.1:13002` từ máy local.
  Tunnel là kết nối tạm thời, không phải dịch vụ tự khởi động cùng máy.
  Lệnh tạo lại ở [hướng dẫn deploy](../deploy/sandbox/README.md).
- Artifact tiếp tục dùng lab cũ, gồm model v4 đã audit; active pointer chưa đổi.
- Log ứng dụng: `~/Workplace/dubbing/.runtime/logs/office-lunch-{api,frontend,worker}.log`.

Đối chiếu trước/sau: PID các dịch vụ VideosFlow, Studio, Demucs, Faster Whisper,
Pyannote và OpenClaw giữ nguyên. Những worker Omnivoice/Pyannote đã dừng từ trước
vẫn dừng. Không start/restart VM, database, container hạ tầng hoặc dịch vụ khác.

## Phần còn lại

Tiếp tục chẩn đoán/phục hồi Teradata theo ràng buộc giữ nguyên dữ liệu; sau đó
activate model v4, sync, publish, nghiệm thu CRUD/filter/outbox và bật worker
duy nhất. Xem [biên bản sự cố](Incident-2026-11-02.md) và [Results](Results.md).
