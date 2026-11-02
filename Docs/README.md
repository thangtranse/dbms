# Tài liệu OfficeLunch

- [Teradata](Teradata.md): SQL, kiến trúc và sandbox.
- [Qdrant](Qdrant.md): vector và vai trò trong ứng dụng.
- [Backend/API](API.md): endpoint, lỗi và trạng thái đồng bộ.
- [Kết quả và trạng thái nghiệm thu](Results.md): số đo thực và các bước đã xác minh.
- [Lịch sử triển khai](History.md): thay đổi, sự cố và bằng chứng theo ngày.
- [Vận hành và phục hồi](Operations.md): kiểm tra kết nối, reboot và đổi model.
- [Sự cố Teradata 02-11](Incident-2026-11-02.md): bằng chứng lỗi WAL và phạm vi bị chặn.
- [Benchmark](Benchmark.md): Trans2Vec, chống leakage và giới hạn kết luận.
- [Vận hành](../backend/README.md): local Compose, native sandbox CLI và artifact.

```mermaid
flowchart LR
  FE[Next.js local] --> API[FastAPI local]
  API --> TD[Teradata sandbox VM]
  API --> Q[Qdrant sandbox container]
  TD --> W[Outbox worker local]
  W --> Q
  CLI[Training / benchmark CLI sandbox] --> TD
  CLI --> Q
  CLI --> A[Versioned artifacts]
  A --> API
  A --> W
```

Dữ liệu nghiên cứu giữ mã item/yes-no gốc; tên món, giá, user và ngữ cảnh demo
được đánh dấu synthetic. Đây không phải bằng chứng về ý nghĩa thực của mã item.
