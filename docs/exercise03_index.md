# Bài 3 — Chỉ mục thứ hai theo nghiệp vụ

Issue: https://github.com/NMinZ17/coursehub-demo/issues/6

## Truy vấn được chọn

Thống kê số lượt hủy đăng ký theo ngày của một lớp trong một khoảng thời gian.
Truy vấn dùng bind parameter cho lớp, loại sự kiện và hai mốc thời gian:

```sql
SELECT occurred_at::date AS event_date, COUNT(*) AS event_count
FROM enrollment_events
WHERE class_section_id = :class_section_id
  AND event_type = :event_type
  AND occurred_at >= :start_at
  AND occurred_at < :end_at
GROUP BY occurred_at::date
ORDER BY event_date;
```

Khoảng thời gian là `[start_at, end_at)`: bao gồm thời điểm bắt đầu và loại trừ
thời điểm kết thúc. Ví dụ tháng 12/2025 có `start_at=2025-12-01 00:00:00` và
`end_at=2026-01-01 00:00:00`. Không áp dụng hàm lên `occurred_at` trong `WHERE`,
để PostgreSQL có thể sử dụng khoảng trên cột gốc của index.

## Thiết kế index

```sql
CREATE INDEX idx_enrollment_events_section_type_time
ON enrollment_events (class_section_id, event_type, occurred_at);
```

`class_section_id` đứng đầu để giới hạn dữ liệu theo lớp, tiếp theo là điều kiện
bằng `event_type`; `occurred_at` đứng sau hai cột lọc bằng để tìm khoảng thời gian
trong nhóm đã chọn. Hai cột điều kiện bằng có thể đổi chỗ đối với truy vấn dùng
đầy đủ cả hai, nhưng đặt lớp trước còn phù hợp với việc đọc riêng lịch sử một lớp.
Không tạo index cho mọi cột. Không thêm `dataset` vì truy vấn nghiệp vụ không lọc
theo bộ dữ liệu thử. Index đầu tiên của tuần 4
`(dataset, student_id, occurred_at DESC)` được giữ trong benchmark.

Index tăng dung lượng lưu trữ và chi phí `INSERT`/`UPDATE`/`DELETE`. Trên bảng nhỏ
hoặc điều kiện chọn phần lớn dữ liệu, PostgreSQL vẫn có thể chọn sequential scan.
Benchmark không tắt sequential scan và không ép planner dùng index.

Tệp triển khai là `database/13_enrollment_events_business_index.sql`; tệp rollback
là `database/13_enrollment_events_business_index_rollback.sql`. Mỗi tệp có
transaction. Rollback chỉ xóa index, không xóa các sự kiện.

## Đo trước/sau có thể lặp lại

Chạy từ thư mục gốc checkout riêng, sau khi cài `backend/requirements-dev.txt`
và cấu hình kết nối theo `docs/exercise01_events.md`:

```powershell
python -m backend.tests.benchmark_index --output docs/evidence/index_benchmark.json
python -m pytest backend/tests/test_business_index.py -v
```

Script chỉ ghi vào schema thử có tên ngẫu nhiên do `isolated_database()` tạo.
Nó sinh 100.000 sự kiện xác định, phân bố trên bốn lớp, hai loại sự kiện và một năm.
Script giữ cùng dữ liệu, tham số và index thứ nhất cho hai trạng thái; xác nhận
index thứ hai chưa tồn tại trước lần đo. Mỗi trạng thái chạy một lượt làm nóng,
sau đó năm lượt `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, lấy trung vị thời gian.
Script lưu tất cả plan, số dòng, tham số, phiên bản PostgreSQL, shared hit/read,
và đối chiếu kết quả truy vấn trước/sau. Không ghi các con số giả làm kết quả đo.

Khi đọc `docs/evidence/index_benchmark.json`, so sánh:

| Chỉ số | Trước | Sau |
| --- | --- | --- |
| Tổng số dòng | `total_rows` | giữ nguyên |
| Execution time trung vị | `before.median_execution_ms` | `after.median_execution_ms` |
| Planning time trung vị | `before.median_planning_ms` | `after.median_planning_ms` |
| Shared hit/read blocks | `before.median_shared_*` | `after.median_shared_*` |
| Loại scan và Index Cond | `before.plans` | `after.plans` |

Tốc độ đo phụ thuộc máy, cache và lượng dữ liệu; không xem một tỷ lệ tăng tốc là
cam kết hiệu năng production. Bộ dữ liệu xác định giúp tái lập nội dung truy vấn,
không làm thời gian chạy giống tuyệt đối giữa các máy.

Phần “trước” và “sau” trong `docs/week04_notes.md` cũ đều dùng cùng index
`idx_enrollment_events_dataset_student_time`, nên không dùng hai plan đó làm bằng
chứng cho hiệu quả của index mới.

## Ca đúng, ca lỗi và khôi phục dữ liệu

| Ca | Kiểm tra |
| --- | --- |
| Thống kê có dữ liệu | Kết quả trước/sau hoàn toàn giống nhau |
| Không có dữ liệu | Lớp không tồn tại trả danh sách rỗng |
| Biên thời gian | Bao gồm đầu kỳ, loại trừ đầu kỳ tiếp theo |
| Thứ tự cột index | Đúng `(class_section_id, event_type, occurred_at)` |
| Timestamp sai | PostgreSQL từ chối với SQLSTATE `22007`; transaction được rollback |
| Tạo trùng index | PostgreSQL từ chối với SQLSTATE `42P07` |
| Rollback index | Index biến mất, số dòng và kết quả truy vấn giữ nguyên |

Sau mỗi test và sau benchmark, context manager xóa toàn bộ schema thử, kể cả
bảng, index và identity sequence của schema đó. Dữ liệu và sequence gốc không
được chỉnh sửa. `cleanup_confirmed=true` chỉ được ghi vào bằng chứng sau khi
context khôi phục xong và kiểm tra snapshot CSDL gốc. Nếu test lỗi, phần `finally`
của context vẫn thực hiện dọn schema thử.

Nguồn giải thích nguyên tắc B-tree nhiều cột:
https://www.postgresql.org/docs/18/indexes-multicolumn.html
