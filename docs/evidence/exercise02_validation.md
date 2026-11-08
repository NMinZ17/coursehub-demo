# Kết quả Bài 2 — 08/11/2026

`python -m pytest backend/tests/test_rollback.py -v`: 3 ca PASS trên PostgreSQL 18.6.

1. Ca lỗi: listener xác nhận INSERT enrollments đã hoàn tất rồi mới thử INSERT
   enrollment_events. PostgreSQL từ chối với SQLSTATE 23514 và đúng constraint
   ck_enrollment_events_type. HTTP 409. Đọc bằng kết nối riêng xác nhận số dòng
   và SHA-256 toàn bộ nội dung hai bảng giống trước request.
2. Ca đúng: HTTP 201; mỗi bảng tăng một dòng, JOIN khớp sinh viên/lớp/sự kiện.
3. Production app: endpoint demo trả 404 và không có trong OpenAPI.

Schema thử và identity sequence được xóa sau từng ca, kể cả ca đã commit.
Guard kiểm tra dữ liệu, metadata cột, index và sequence của schema nguồn không
đổi. Không đưa demo vào production router.
