# Chẩn đoán và phương án phục hồi Teradata — 2026-11-06

## Kết quả hiện tại

Chưa sửa xong Teradata. Khởi động bình thường từ bản sao bộ đĩa tiếp tục lỗi
WAL 5192 ở AMP 1, 2 và 3, rồi bị chặn bởi crash limit 13857. Chưa logon SQL
được; không thể xác nhận tính toàn vẹn của dữ liệu ứng dụng.

## Bằng chứng và bảo toàn dữ liệu

- Trước thao tác, VM đang tắt. `qemu-img check` không báo corruption dữ liệu
  QCOW2: disk1/disk2 mỗi ổ có 2 leaked clusters, công cụ mô tả là chỉ lãng phí
  dung lượng; disk3 không có lỗi. Không sửa refcount hoặc compact ổ để tránh
  tạo cảm giác đã xử lý nguyên nhân WAL.
- Copy đủ ba overlay lúc không có QEMU chạy vào
  `/Users/gper/Workplace/dubbing/office-lunch-lab/recovery-20261106/`.
  SHA-256 của từng bản sao khớp nguồn, có `manifest.json` ghi đường dẫn backing.
  Đây là snapshot trạng thái lỗi hiện tại, **không phải backup dữ liệu khỏe**.
- Cả OVF và ba VMDK nguồn đều khớp manifest SHA-256 của bộ cài.
- Tạo lớp QCOW2 ghi riêng trong `recovery-20261106/working/overlays`, backing
  vào ba bản copy, rồi chạy cùng guest Teradata trên sandbox bằng launcher
  hiện có với `VANTAGE_RUNTIME_DIR` riêng. Không tạo server trên máy local.
- Guest boot bình thường, TPA tự khởi động và thử phục hồi file system. Log mới:

  ```text
  2026-11-06T01:53:43Z WAL 5192, VPROC 3, fsustart
  2026-11-06T01:53:53Z WAL 5192, VPROC 2, fsustart
  2026-11-06T01:54:03Z WAL 5192, VPROC 1, fsustart
  2026-11-06T01:54:09Z Crash limit 13857
  PDE state is RUN/READY.
  DBS state is 0/-1: DBS is not running
  ```

- Stack nằm trong `wixlockwdb / wruprocesswal / idxbldfsys`; không phải lỗi
  FastAPI, credentials hoặc mạng. Chưa xác định nguyên nhân gốc của WAL hỏng.
- Thu thập log chẩn đoán, sau đó yêu cầu `systemctl poweroff` bình thường trong
  guest thử. Không kill cưỡng bức, không clear WAL, không sysinit/reset dữ liệu.
- Đã xác nhận QEMU bản thử thoát và cổng 1025 không còn listener. Hash lại sau
  lần thử: cả ba overlay gốc và cả ba bản backup vẫn khớp manifest trước boot;
  lưu `post-attempt-validation.json` làm bằng chứng không ghi vào bộ đĩa giữ lại.

Bằng chứng raw: `backend/artifacts/teradata-recovery-20261106/` local (gitignored)
và `office-lunch-lab/recovery-20261106/` sandbox. Các VMDK backing vẫn cần giữ
nguyên bên cạnh snapshot để bộ đĩa đọc được; không chỉ copy riêng một QCOW2.

## Hai hướng xử lý

**Quyết định ban đầu của người dùng ngày 06-11 (sau đó được thay thế):** giữ dữ liệu cũ, chờ phương án từ
DBA/Teradata Support. Dừng thử sửa cho tới khi có phương án cụ thể được xem xét;
không dựng bộ đĩa nền sạch, import lại dữ liệu hoặc bỏ WAL. Giữ nguyên các ổ
gốc, snapshot lỗi, lớp ghi thử và diagnostics để phục vụ phân tích.

**Ủy quyền tiếp theo cùng ngày:** người dùng yêu cầu khắc phục và cho phép
xóa dữ liệu hiện có. Đã chuyển sang hướng dựng bộ overlay sạch trên sandbox,
import food/demo và activate model v4. Bộ đĩa lỗi vẫn giữ lại tại
`teradata/runtime/vantage-express/overlays-corrupt-20261106/`, ngoài snapshot
đã có. Không khẳng định dữ liệu ứng dụng cũ đã được cứu; xem lịch sử/báo cáo
rebuild để biết kết quả mới. [Dựng lại và nghiệm thu đã hoàn tất](Teradata-Rebuild-2026-11-06.md),
gồm SQL/model/Qdrant readiness và kiểm tra dữ liệu qua restart.

### Giữ dữ liệu cũ

Giữ nguyên bộ đĩa và nhờ DBA/Teradata Support phân tích WAL/file-system recovery
trên bản sao. Chưa có quy trình sửa WAL cụ thể đã được xác minh phù hợp với
instance này. Tài liệu [WAL của Database Engine 20](https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/Database-Utilities/Ferret-Utility-ferret/Write-Ahead-Logging-WAL)
giải thích redo/TJ phục vụ consistency và rollback, đồng thời mô tả việc sửa WAL
thuộc phạm vi công cụ hỗ trợ của Teradata. Không bỏ WAL để ép SQL lên rồi gọi
đó là phục hồi dữ liệu thành công.

### Khôi phục khả năng chạy demo bằng bộ đĩa mới trên sandbox

Phương án này cần người dùng xác nhận vì chưa thể phục hồi những thay đổi đã
ghi qua ứng dụng mà chỉ tồn tại trong Teradata lỗi:

1. Giữ nguyên overlay gốc, snapshot lỗi và log. Tạo bộ overlay riêng backing
   vào các VMDK nguồn đã kiểm checksum, dùng đúng VM/runtime sandbox hiện có.
2. Khởi động database nền sạch, tạo riêng schema OfficeLunch, import lại food
   theo checksum cùng snapshot demo trong repo.
3. Activate model v4 đã train/audit, dùng collection Qdrant có phiên bản mới,
   publish lại kết quả đã có artifact; không xóa collection cũ.
4. Kiểm tra CRUD/filter/outbox, readiness, rồi bật một worker sandbox. Đối chiếu
   và phục hồi thêm dữ liệu nghiệp vụ cũ sau này nếu giải mã/khôi phục được.

Đây là dựng lại dữ liệu ứng dụng từ nguồn có sẵn, không phải chứng minh mọi
giao dịch cũ đã phục hồi. Chưa thực hiện hướng này vì yêu cầu trước của người
dùng là giữ nguyên dữ liệu và chưa có backup khỏe trước sự cố.
