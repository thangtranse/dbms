# Version theo Git commit cho mỗi build

Thanh trên cùng của FE hiển thị `Phiên bản <12 ký tự commit>` và thời điểm build
UTC. Bấm phiên bản để mở `/build-info`. API trả cùng cấu trúc tại `/api/version`
(qua FE proxy hoặc trực tiếp cổng 8002 trên sandbox); liveness cũng có trường
`build`. Hai endpoint version không cần database và trả `Cache-Control: no-store`.

| Trường | Ý nghĩa |
|---|---|
| `version` | SHA rút gọn 12 ký tự, thêm `-dirty` nếu source chưa commit |
| `commit` | SHA Git đầy đủ của source lúc build |
| `shortCommit` | 12 ký tự đầu của SHA |
| `builtAt` | Thời điểm tạo artifact build, UTC ISO-8601 |
| `dirty` | true/false; null nếu không biết source commit |

Metadata được cố định lúc build/start process, không lấy Git HEAD ở mỗi request.
Chỉ pull source hoặc restart process không tự biến artifact FE cũ thành version
mới. Không dùng thời điểm commit làm thời điểm build. File `build-info.json` là
output được gitignore, không commit metadata để tránh vòng lặp đổi chính SHA.

## Native sandbox

Dùng `/bin/bash deploy/sandbox/build.sh` từ checkout đã cập nhật trên main.
Script chạy npm ci/build và copy metadata FE sang `backend/build-info.json`,
để FE/API native hiển thị cùng commit và cùng thời điểm build. Dừng đúng process
OfficeLunch trước build; start lại các process đã chạy sau build thành công.
Không thay `.env`, model, schema hoặc database khi chỉ cập nhật version.

```bash
cd /Users/gper/Workplace/dubbing/dbms
/bin/bash deploy/sandbox/build.sh
curl http://127.0.0.1:18300/build-info
curl http://127.0.0.1:18300/api/version
```

`npm run build`/`npm run dev` tự tạo metadata FE bằng prebuild/predev. Nếu build
thủ công native, cần copy `office-lunch/build-info.json` sang backend trước khi
restart API; helper đã làm bước này sau khi build FE thành công.

## Docker / Compose

`make build`, `make up`, `make up-all` tự truyền SHA và dirty flag từ checkout
vào build args của cả hai image. Docker không cần chứa `.git`. Nếu build từ CI
hoặc gọi Docker/Compose trực tiếp, truyền `BUILD_COMMIT` đầy đủ và `BUILD_DIRTY`:

```bash
BUILD_COMMIT="$(git rev-parse HEAD)" BUILD_DIRTY=false docker compose build api office-lunch
```

Chỉ dùng `BUILD_DIRTY=false` khi source đã sạch; dùng true cho source chưa commit.
Nếu không có Git/build arg, version là `unknown`, không giả định package version
hoặc commit của lần deploy trước. FE/API Docker build độc lập có thể khác thời
điểm build; commit phải khớp nếu triển khai cùng source. Build dùng cache toàn bộ
vẫn giữ thời điểm tạo artifact cũ.

## Kiểm thử và rollout

```bash
cd office-lunch
npm run test:build-info
```

Test tạo repo Git fixture thật để kiểm tra clean/dirty, chặn SHA khai báo khác
checkout, kiểm tra fallback khi không có Git. Backend kiểm tra metadata không
lộ trường ngoài danh sách và version endpoint không phụ thuộc database.

Khi deploy, đối chiếu `/build-info`, `/api/version`, Git HEAD và trạng thái clean,
rồi kiểm tra readiness cùng log. Bản ghi rollout thực tế lưu dưới
`dbms/.runtime/deployments/<commit>.json` trên sandbox để không làm checkout dirty
ngay sau khi build; dữ liệu này không phải thành phần của source commit.
