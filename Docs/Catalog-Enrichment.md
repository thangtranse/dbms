# Catalog có nguồn — cập nhật 06-11-2026

## Phạm vi và giới hạn

`food.txt` chỉ có mã số và giao dịch. Không có bằng chứng nối mã nghiên cứu với
món ăn thật. Catalog dưới đây là lớp demo có nguồn; ánh xạ ID vẫn là tổng hợp,
không phải khôi phục danh tính món gốc hay xác nhận chất lượng semantic của model.

Lần v1 đã gán luân phiên 36 mẫu cho 1.523 mã, tạo tên `Demo <ID>`, 5 URL ảnh,
34 bộ tag và 12 mức giá. Việc kiểm tra có đủ trường đã không phát hiện thiếu
đa dạng. Phiên bản v2 thay cơ chế đó, không thêm hậu tố để tạo tên khác giả tạo.

## Nguồn và thu thập

- Cookbeo: <https://cookbeo.com/sitemap.xml>, trường Recipe JSON-LD trên từng
  trang công thức; chỉ lấy tên, URL ảnh, nhóm món và vùng ẩm thực. Không sao chép
  bài viết, hướng dẫn nấu hoặc tải ảnh vào repository.
- TheMealDB: <https://www.themealdb.com/api.php>, API phát triển công khai theo
  chữ cái; lấy tên, URL ảnh, nhóm, vùng ẩm thực và danh sách tên nguyên liệu.
  Dùng cho sandbox/demo, không coi test key là khóa production.
- `backend/data/catalog-v2.json` lưu snapshot và ánh xạ ổn định. Mỗi món có
  `sourceUrl`, `sourceProvider`, `retrievedAt`, `mappingBasis` trong SQL/API.

Quy trình tái tạo từ root repository:

```bash
mkdir -p .runtime/catalog-sources
curl --fail https://cookbeo.com/sitemap.xml -o .runtime/catalog-sources/cookbeo-sitemap.xml
python3 backend/scripts/fetch_catalog.py
python3 backend/scripts/check_catalog_images.py
python3 backend/scripts/assign_catalog.py
```

Loại trùng tên chuẩn hóa và URL ảnh, loại tên/ảnh đã dùng bởi 36 món demo ban
đầu. Kiểm tra HEAD xác nhận HTTP 200 và Content-Type image; không phải kiểm
chứng bằng mắt hoặc bằng perceptual hash rằng mọi ảnh có nội dung khác nhau.
Ba URL ảnh không đạt đã bị loại. Kết quả ánh xạ: 1.523 công thức, trong đó 734
Cookbeo và 789 TheMealDB, không có mã cần lặp lại công thức để lấp chỗ trống.

Tag lấy từ nguồn; nhiều món có thể cùng nguyên liệu/nhóm. Không ép tag khác
nhau hoặc tự suy diễn các nhãn sức khỏe, dị ứng, vegan từ ảnh/tên món.

## Giá và phân nhóm

Nguồn công thức không có giá bán: SQL giữ giá 0 theo contract cũ nhưng đánh dấu
`priceStatus=unknown`. Không có nghĩa là miễn phí. `categoryId=null` chờ rà soát
vì taxonomy 7 nhóm hiện có không bao phủ toàn bộ công thức. `suggestedCategoryId`
chỉ là đề xuất theo quy tắc tên, chưa phải phân loại đã xác minh; nhóm gốc vẫn
nằm trong tag. FE sandbox hiện có hiển thị “Chưa gán giá” cho các dòng này.

Qdrant đặt `mapped=false` cho các công thức chưa có giá/phân nhóm. Gợi ý theo
ngân sách chỉ dùng các món đã có metadata phù hợp trước đó. Không dùng 0 như
giá bán để đưa món chưa định giá vào kết quả. Mã local bổ sung điều kiện giá > 0
trong worker và bộ lọc/revalidation recommend; chưa deploy thay đổi mã ứng dụng.

## Cập nhật và bảo trì

`python -m ol.cli enrich-catalog` chỉ preview. Thêm `--apply --backup <path>`
để ghi. Chỉ thay placeholder nguyên vẹn hoặc metadata v1 chưa chỉnh tay; bảo vệ
món đã sửa, giữ ID, cluster, tọa độ, modelVersion và toàn bộ research data.

Tạm dừng riêng API/worker trước khi ghi để tránh khóa chéo Teradata ANSI. Lệnh
SQL batch và outbox cùng transaction, backup đầy đủ trước khi ghi. Không dùng
lại lệnh chạy từng dòng của v1.

`sync_catalog_batch(<backup-path>)` chỉ dùng trong khoảng bảo trì: lấy vector
hiện có từ Qdrant, kiểm tra modelVersion và toàn bộ ID, backup point cũ, upsert
theo batch với nguyên vector và cập nhật applied theo đúng revision. Không
huấn luyện, activate hoặc tạo vector mới. Chạy kiểm chứng rồi bật lại đúng
process đã chạy trước bảo trì.

Sandbox giữ main commit `4771ae1`; module và snapshot được staging trong
`/Users/gper/Workplace/dubbing/dbms/.runtime/catalog-v2/`, không ghi đè checkout,
không pull/build/push ứng dụng. Backup: `sql-before-v2.json`,
`qdrant-before-v2.json` trong thư mục đó. Code/UI local cần deploy theo quy trình
thông thường để hiện link nguồn trực tiếp và áp dụng thay đổi cho các lần import.

## Kết quả kiểm chứng v2

- 1.559 tên chuẩn hóa và 1.559 URL ảnh khác nhau trên toàn danh mục; không khẳng
  định khác nhau tuyệt đối về nội dung ảnh hoặc ý nghĩa tên giữa các ngôn ngữ.
- 1.523 dòng sourced-demo, 1.364 bộ tag khác nhau; 36 dòng cũ không đổi.
- Toàn bộ vector của 1.523 point trùng chính xác backup Qdrant trước cập nhật;
  cluster, tọa độ và modelVersion của cả danh mục giữ nguyên.
- SQL/outbox/Qdrant nhất quán, pending=0, FE proxy `/api/clusters` trả 1.559 món
  synced; readiness HTTP 200; API/worker/frontend RUNNING.
- Gọi recommend ngân sách dưới 35.000 trả 4 món có giá > 0, không có món giá chưa
  xác minh bị diễn giải thành miễn phí.
- Ba kiểm thử catalog đạt trên Python sandbox; TypeScript và `git diff --check`
  đạt tại local. Chưa thực hiện kiểm chứng giao diện bằng browser.
