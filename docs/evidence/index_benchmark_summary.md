# Bằng chứng thực nghiệm Bài 3

Đo ngày 08/11/2026 trên PostgreSQL 18.6, Windows x86-64. Số liệu gốc và toàn bộ
execution plan nằm trong [index_benchmark.json](index_benchmark.json).

- 100.000 sự kiện, giữ nguyên dữ liệu và tham số trước/sau.
- Giữ index thứ nhất `(dataset, student_id, occurred_at DESC)` trong cả hai trạng thái.
- Một lượt làm nóng và năm lượt đo mỗi trạng thái; không ép planner.
- Truy vấn tháng 12/2025, lớp WEB-01, CANCELLED: 412 sự kiện trong sáu ngày.

| Chỉ số | Trước index thứ hai | Sau index thứ hai |
|---|---:|---:|
| Execution time trung vị | 1,029 ms | 0,214 ms |
| Shared hit blocks trung vị | 468 | 315 |
| Shared read blocks trung vị | 0 | 0 |
| Dòng do Bitmap Index Scan trả | 8.485 | 412 |
| Dòng bị loại thêm bởi filter | 8.073 | 0 |

Trước: Bitmap Index Scan dùng index thứ nhất, rồi lọc lớp/loại sự kiện.
Sau: Bitmap Index Scan dùng `idx_enrollment_events_section_type_time`, lọc đúng
lớp, loại và khoảng thời gian. Nội dung kết quả hoàn toàn giống nhau. Thời gian
trung vị giảm khoảng 4,81 lần trong phép đo này; kết quả phụ thuộc máy/cache,
không phải cam kết tốc độ production.

`results_equal=true`, `first_index_present=true`, `cleanup_confirmed=true`.
Schema thử chứa dữ liệu và index được xóa sau đo; snapshot schema nguồn, bao
gồm sequence, được đối chiếu bằng nhau. Năm ca pytest riêng của bài 3 đã PASS.
