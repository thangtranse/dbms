# Phương pháp thực nghiệm

## Nguồn và dữ liệu

Nguồn thuật toán: [Trans2Vec](https://github.com/nphdang/Trans2Vec).
Bản Python này tái triển khai cách ghép vector Ind (trung bình hai PV-DBOW)
và Joi (học chung item/FI token), không cam kết tái lập kết quả bài báo.
Mã tham chiếu cũ học embedding trước khi chia tập; bản này chỉ fit trên train.
FP-growth thay chương trình FIM .NET. Singleton cũng là frequent itemset.

Food gồm mã item và nhãn yes/no. Giá/tên món, thời tiết, người dùng là metadata
bổ sung tổng hợp; không dùng để đo chất lượng phân loại của dataset gốc.
Bộ food hiện có không có cặp item đạt support 0.006 trên toàn tập: cần đọc số
pattern thật trong artifact, không khẳng định Trans2Vec luôn vượt baseline.
Itemset có thể chỉ gồm singleton ở ngưỡng mặc định.

Tách 80/20 bằng StratifiedGroupKFold năm fold, lấy fold đầu cho từng seed.
Group theo tập item đã sắp xếp, tránh giao dịch cùng nội dung xuất hiện ở cả
train/test, kể cả khi nhãn khác nhau. ID gốc theo dòng; giữ list token gốc cho
embedding và checksum file. Không ép chính xác 3200/800 nếu grouping làm lệch.
Không dùng nhãn test để fit, chọn hyperparameter hay chọn model phục vụ; mặc định
Joi seed 0 cố định. Item ngoài vocabulary suy luận vector zero, không bịa vector;
benchmark từ chối zero vector vì cosine không xác định.

## Hai phép đánh giá tách biệt

1. Chất lượng biểu diễn: Bag-of-items, Trans2Vec-Ind, Trans2Vec-Joi + LinearSVC.
   Báo Accuracy/Macro-F1 và confusion theo seed, trung bình 10 seed trên UI.
2. Hiệu năng DB: cùng vector Joi, corpus train, query test, kNN k=15, hòa phiếu
   chọn no. Không dùng SVM trong phép đo database.

Teradata SQL join vector và query theo chiều rồi SUM và chuẩn hóa cosine.
Qdrant exact tắt xấp xỉ; Qdrant ANN dùng HNSW m=16, ef_construct=100, ef=128, full_scan_threshold=10 KiB (mức nhỏ nhất server 1.19.2 chấp nhận), thấp hơn corpus 1.6 MiB để dùng HNSW.
Cấu hình gộp về một segment tối ưu; ghi số segment thực trong manifest.
Đợi indexed_vectors_count đạt corpus trước khi đo, không gắn tên ANN cho full scan.
Ground truth NumPy float64 trên float32 input, chuẩn hóa lại để so cosine.
Recall@k chấp nhận các điểm hòa trong sai số 1e-6 tại biên; điểm hòa không được
thay thế láng giềng có score cao hơn biên. Sai số score exact tối đa 1e-5.

50 warmup trước mỗi lượt, năm lượt toàn bộ test, concurrency 1/4. Luân phiên
thứ tự engine giữa các lượt; dùng connection tái sử dụng trong warmup/đo.
Không gọi bất kỳ lượt nào cold-cache. Ghi percentile của các query thành công,
throughput và error rate riêng. Ghi setup/import/index riêng khỏi query latency.
Raw JSONL giữ query ID, hàng xóm, score, độ trễ, dự đoán và lỗi theo từng query.
Model manifest chứa versions/seeds/splits/hash; benchmark manifest chứa host,
endpoints, HNSW và cấu hình. Không lưu mật khẩu/API key vào artifact.

## Giới hạn kết luận

Runner trên Intel sandbox, Teradata trong VM, Qdrant trong Docker: CPU, RAM,
network và tầng ảo hóa không tương đương. Kết quả mô tả cấu hình đang triển khai,
không chứng minh ưu thế phổ quát của một engine. Dataset chỉ 4.000 dòng; không
đại diện tải lớn hay scale-out. Không so tốc độ API Python và Rust ở đây.

Teradata thể hiện SQL quan hệ, transaction và thống kê trong ứng dụng; Qdrant
thể hiện top-k similarity cùng lọc payload. Benchmark cosine là bài toán chung,
không phải thước đo toàn bộ khả năng của cả hai hệ thống.

Teradata được COLLECT STATISTICS trên run, chiều và khóa truy vấn trước khi đo.
Nạp vector theo batch 4096 thành phần có commit riêng; đây là setup dữ liệu
thực nghiệm chưa publish, không phải transaction nghiệp vụ. `--reuse-data-run`
chỉ tái sử dụng corpus SQL đã chuẩn bị từ đúng training run/seed/hash và đủ số
chiều; manifest ghi rõ reuse, thời gian validation tách khỏi thời gian import.

Trong thiết kế này SQL đọc query vector đã nạp vào `benchmark_queries`, còn
Qdrant nhận vector trong request. Độ trễ là round-trip của hai cách triển khai
truy vấn, không phải phép đo CPU engine độc lập với giao thức/client. Các dịch
vụ khác trên sandbox giữ nguyên trạng thái, đây không phải máy benchmark cô lập.

Trường `trainSeconds` hiện giữ tên wire cũ nhưng đo tổng đoạn pipeline của từng
phương pháp (fit biểu diễn/classifier, infer test và lưu model), không phải chỉ
CPU fit thuần. UI ghi “Pipeline giây”. Thời gian này không nằm trong các lượt
đo query database; không dùng nó để so tốc độ query hai engine.

Các run mới tạo cặp bảng `bv_<hash>` / `bq_<hash>` riêng trong schema ứng dụng,
tránh quét dữ liệu thí nghiệm cũ làm lệch thời gian. Manifest/prepared.json lưu
tên bảng để reuse có kiểm tra. Run kiểm chứng `food-bench-v4` dùng corpus legacy
`food-bench-v2` trong hai bảng gốc, lúc đo chỉ chứa đúng một corpus/query set.

## Numerical regression gate

Gensim 4.4.0 có [lỗi BLAS #3665](https://github.com/piskvorky/gensim/issues/3665)
khi một dot product trả đúng -1. Model mới dùng Gensim 4.3.3, NumPy 1.26.4 và
SciPy 1.13.1, có probe âm/dương qua BLAS wrapper trước train/load và test hồi quy.
Run database `food-bench-v4` giữ nguyên vector v2 cũ để bảo toàn phép đo;
`annotations.json` đi kèm được publish riêng và hiển thị trên UI. Kết quả retrieval
được đối chiếu với NumPy trên cùng vector, còn chất lượng mô hình phục vụ được
báo từ run mới đã qua numerical gate. Không gộp hai phép đánh giá này.
