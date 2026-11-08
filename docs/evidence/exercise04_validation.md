# Kết quả Bài 4 — 08/11/2026

`python -m pytest backend/tests/test_migration_002.py -v`: 9 ca PASS trên
PostgreSQL 18.6. Mỗi ca áp dụng tệp SQL thật lên bảng đã có ba sự kiện commit.

- So sánh toàn bộ bảy cột cũ: giữ nguyên khi thêm note và khi rollback.
- Metadata: VARCHAR(200), nullable; registry có đúng version 002.
- 200 ký tự ASCII, 200 ký tự Unicode và NULL: lưu đúng.
- 201 ký tự: SQLSTATE 22001, các dòng không thay đổi.
- Chạy trùng migration/rollback: báo lỗi, không có thay đổi dở dang.
- Cố ý làm INSERT registry lỗi sau ALTER: cột vừa thêm cũng được rollback.
- Rollback khi đã có note: giữ sự kiện, xóa mọi nội dung ghi chú. Áp dụng lại
  chỉ tạo note NULL; không phục hồi ghi chú đã mất.

Lần chạy tổng hợp cuối: **33 pytest PASS** (16 bài 1, 3 bài 2, 5 bài 3,
9 bài 4), 1 cảnh báo deprecation của TestClient. Thời gian 5,28 giây.
Bản tóm tắt công khai: [validation_summary.json](validation_summary.json).

`source_preserved=true`; kiểm tra số dòng, nội dung dữ liệu, metadata cột,
index và sequence đều bằng nhau trước/sau. Schema thử được xóa trong finally
sau mỗi ca. Báo cáo snapshot đầy đủ và JUnit của máy cục bộ được giữ riêng,
không công khai tên máy, đường dẫn cá nhân hoặc metadata CSDL cục bộ cụ thể.
