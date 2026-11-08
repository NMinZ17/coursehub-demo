# CourseHub

FastAPI và PostgreSQL cho bài thực hành Cơ sở dữ liệu Web và hệ thống thông tin.

## Bài tập tiếp nối tuần 4

Nhánh nền `week04-transaction-index` đã có schema, seed, transaction đăng ký và
migration 001 tạo `enrollment_events`.

- [Bài 1: API lịch sử, Postman và cách chạy kiểm thử](docs/exercise01_events.md).
- Các bài tiếp theo bổ sung tài liệu riêng trong `docs/` cùng từng Pull Request.

```powershell
python -m pip install -r backend/requirements-dev.txt
# Đặt DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD cho PostgreSQL thử nghiệm,
# hoặc đặt COURSEHUB_ENV_FILE trỏ đến tệp dotenv riêng không đưa vào Git.
python -m pytest -v
```

Integration test tạo schema ngẫu nhiên dùng một lần, dọn trong finally và đối
chiếu schema nguồn trước/sau, kể cả dữ liệu và sequence. Tài khoản thử nghiệm
cần quyền CREATE schema. Không chạy legacy script `week04_concurrency_test.py`
để kiểm chứng cơ chế khôi phục mới; script đó không thuộc bộ pytest này.

Workflow GitHub Actions dùng PostgreSQL 18 riêng và lưu artifacts kiểm thử.
