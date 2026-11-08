# Kết quả Bài 1 — 08/11/2026

Môi trường: Windows, Python 3.14.8, PostgreSQL 18.6, SQLAlchemy 2.1.6,
FastAPI 0.162.0, pytest 9.2.0. Chạy trên bản làm việc riêng.

- `python -m pytest backend/tests/test_enrollment_events.py -v`: 16 ca PASS.
- Newman: 10 request, 26 assertion, 0 lỗi. Có dữ liệu, không có dữ liệu, lọc,
  phân trang cùng timestamp, limit 1/100 và các giá trị không hợp lệ đều đúng.
- Báo cáo Newman đầy đủ: [postman_events.json](postman_events.json).
- Server in `POSTMAN_DEMO_CLEANUP_CONFIRMED` sau khi lifespan xóa schema và
  xác nhận snapshot schema nguồn giống trước khi chạy, kể cả sequence.
- Mỗi pytest case cũng xóa schema riêng trong finally và đối chiếu nguồn.

Tất cả thao tác ghi diễn ra trong schema ngẫu nhiên dùng một lần. API nguồn
không được gọi để tạo/xóa dữ liệu thử. Không sửa mã nguồn trong thư mục dự án
gốc khi chuẩn bị PR; nội dung được chuẩn bị trong bản xuất riêng.

Có một cảnh báo deprecation từ phiên bản Starlette mới về adapter httpx của
TestClient; kiểm thử vẫn PASS. Đây không phải lỗi API hoặc rollback.
