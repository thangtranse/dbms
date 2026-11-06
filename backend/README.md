# OfficeLunch backend

Python 3.11 / FastAPI, Teradata SQL Driver, Qdrant client, gensim Doc2Vec,
scikit-learn, mlxtend FP-growth. Chỉ một uvicorn worker, tối đa bốn thread xử lý
route đồng bộ. Kết nối Teradata được tái sử dụng trong pool tối đa bốn phần tử.

## Local (từ gốc repo)

`.env` cần `TERADATA_HOST=100.65.210.21`, credentials sandbox,
`TERADATA_DATABASE=officelunch`, `QDRANT_URL=http://100.65.210.21:6333`,
`QDRANT_API_KEY`, `QDRANT_PREFIX=officelunch`. Không đưa secrets vào FE.
`TERADATA_LOGON_TIMEOUT` mặc định 10 giây để chặn logon chờ vô hạn khi DBS lỗi;
đây không phải timeout cho mọi SQL query. Tham số theo [driver chính thức](https://github.com/Teradata/python-driver#connection-parameters).

```bash
docker compose build api
docker compose run --rm api python -m ol.cli migrate
docker compose run --rm api python -m ol.cli import-food
docker compose up -d --build api office-lunch
curl --fail http://127.0.0.1:8001/api/health/ready
```

Liveness `/api/health/live` chỉ báo process; readiness kiểm tra SQL, model và
hai collection đang phục vụ. FE tại `http://localhost:3000`, OpenAPI tại
`http://127.0.0.1:8001/docs`. API chỉ bind localhost; chưa có đăng nhập.

API thiếu model vẫn phục vụ CRUD/thống kê; recommend trả 503. Không tự động trả
mock data. Mỗi ghi món/bữa ăn cùng event outbox nằm trong một SQL transaction.
Worker duy nhất dùng file lock trên cùng artifact directory, xử lý tuần tự và
chỉ ack revision đã gửi. Không vận hành hai worker ở hai máy trên cùng namespace.
Qdrant lỗi: dữ liệu SQL vẫn giữ, `vectorStatus=pending`; thử lại mỗi 5 giây.
Món có lịch sử không được xóa (409). Món ngoài vocabulary food giữ pending,
không tự tạo vector ngẫu nhiên. Training không tự đọc dữ liệu app vào benchmark.

## Pipeline và benchmark trên sandbox

Bản chạy tách riêng trong `/Users/gper/Workplace/dubbing/office-lunch-lab` để
không ghi đè checkout hoặc `.env` có sẵn. Layout gồm `backend/` và `data/food.txt`.
Dùng uv tạo `backend/.venv` Python 3.11 và cài `backend/requirements.txt`.
Wrapper `backend/run-sandbox.sh` đọc credentials từ `.env` sandbox hiện có,
đặt database endpoint native là `127.0.0.1`, không khởi động database/VM.

```bash
cd /Users/gper/Workplace/dubbing/office-lunch-lab
backend/run-sandbox.sh migrate
backend/run-sandbox.sh import-food
backend/run-sandbox.sh train --run-id food-model-demo-01
ARTIFACT_DIR="$PWD/backend/artifacts" FOOD_PATH="$PWD/data/food.txt" \
  PYTHONPATH="$PWD/backend" OPENBLAS_NUM_THREADS=1 \
  backend/.venv/bin/python backend/tests/verify_artifacts.py food-model-demo-01
backend/run-sandbox.sh activate --run-id food-model-demo-01 --seed 0
backend/run-sandbox.sh sync --drain
backend/run-sandbox.sh benchmark --training-run food-model-demo-01 --run-id food-bench-demo-01
```

`train`: 10 seed (0–9), 128 chiều, 50 epoch, minsup 0.006 mặc định. ID run mới
là bắt buộc: không ghi đè artifact. Dataset/split/model/versions/patterns được
lưu trong `backend/artifacts/<runId>`. Chỉ `manifest.json` có status complete mới
được activate. Collection serving có phiên bản; model cũ chỉ được thay sau khi
collection mới và kết quả SQL hoàn tất. Không tự xóa collection/model cũ.

Sau activate, đồng bộ về local khi worker local chưa chạy:

```bash
rsync -az -e 'ssh -p 22111' \
  gper@100.65.210.21:/Users/gper/Workplace/dubbing/office-lunch-lab/backend/artifacts/ \
  backend/artifacts/
docker compose up -d api office-lunch
```

Chỉ sync các run cần dùng và `active.json`; không cần copy run thử chưa hoàn tất.
Worker chính hiện chạy native trên sandbox; không bật thêm worker local cùng
namespace. Profile `local-worker` chỉ dùng khi chuyển quyền chạy worker về local
và đã dừng worker sandbox.
Không activate model mới khi API đang nhận traffic: dừng riêng API/vector-worker,
activate, copy artifact, rồi start lại hai service. Không dừng database.

`benchmark`: seed 0 của model Joi, corpus train và query test cố định; k=15,
warm-up 50, năm lượt đo với concurrency 1 và 4. SQL tính cosine trên các chiều
ngay tại Teradata; Qdrant chạy exact/ANN với cùng float32. ANN buộc chờ HNSW
index sẵn sàng. Không đánh đồng SQL exact với ANN nếu chưa kiểm tra recall.
Raw JSONL được lưu ngoài summary API. Truy vấn lỗi được tính error rate, không
âm thầm thay kết quả. Benchmark chỉ đọc qua API; không có HTTP endpoint chạy job.

## Tests

```bash
docker compose run --rm api python -m pytest tests -q
# Có ghi test trong schema riêng rồi rollback, không commit dữ liệu test:
docker compose run --rm -e LIVE_DB_TESTS=1 api python -m pytest tests -q
```

Xem [phương pháp thực nghiệm](../Docs/Benchmark.md) và
[hợp đồng API](../Docs/API.md). File seed `data/demo.json` là snapshot UI cũ,
được đánh dấu synthetic; không phải mapping chính thức của food.txt.

Nếu đã có `manifest.json` complete nhưng SQL publish thất bại, không cần đo lại:

```bash
backend/run-sandbox.sh publish --run-id food-bench-v4
```

Publish chạy lại không nhân đôi result; không thay active model. API chọn kết quả
được publish gần nhất. Với run ID đã tồn tại, luôn chọn ID mới khi train/benchmark.

Kiểm thử tích hợp qua FE (chỉ dữ liệu test mới được tạo rồi dọn):

```bash
docker compose run --rm --no-deps -e API_URL=http://host.docker.internal:3000 api python tests/live_smoke.py
# Read-only: ngân sách, chế độ ăn, avoid, tag ngữ cảnh và loại trừ món:
docker compose run --rm --no-deps api python tests/live_filters.py
# Chạy khi vector-worker đã dừng; URL không truy cập được chỉ đổi trong process test:
docker compose run --rm --no-deps -e API_URL=http://host.docker.internal:3000 api python tests/live_outbox.py
```

Các suite LIVE_DB_TESTS dùng cùng schema cần chạy tuần tự. Không chạy hai suite
ghi dữ liệu kiểm thử vào bảng legacy cùng lúc. Xem [numerical gate](../Docs/Benchmark.md)
để biết lý do pin bộ phiên bản ML.
