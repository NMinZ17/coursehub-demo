# Bài 1 — API đọc lịch sử đăng ký

Issue: [#4](https://github.com/NMinZ17/coursehub-demo/issues/4).

## Hành vi API

`GET /enrollment-events` trả mảng JSON. Các bộ lọc đều không bắt buộc:

| Query | Mặc định | Kiểm tra |
|---|---|---|
| `student_id` | không lọc | đúng 8 ký tự, theo schema hiện tại |
| `event_type` | không lọc | `CREATED` hoặc `CANCELLED` |
| `skip` | 0 | số nguyên không âm |
| `limit` | 10 | số nguyên từ 1 đến 100 |

Không có kết quả trả `200 []`, kể cả khi mã sinh viên chưa tồn tại. Tham số sai
trả 422. Truy vấn dùng bind parameter cho mọi giá trị, chỉ nối các đoạn SQL cố
định. Thứ tự là `occurred_at DESC, id DESC`; ID phân định khi hai thời điểm bằng
nhau. OFFSET phân trang ổn định trên dữ liệu không đổi; một request ghi đồng thời
vẫn có thể làm dịch trang. API trả cả dataset demo và performance theo bộ lọc;
benchmark dùng schema riêng nên không làm lẫn sự kiện thử với dữ liệu thật.

Ví dụ:

```http
GET /enrollment-events?student_id=22000001&event_type=CREATED&skip=0&limit=10
```

## Cài và chạy kiểm thử

Dùng checkout riêng chứa PR. Không cần sửa hoặc sao chép `.env` của dự án gốc
vào Git. Chọn tài khoản PostgreSQL dành cho thử nghiệm, có quyền CONNECT và
CREATE schema trên database thử; thư viện không tự tạo database.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
$env:COURSEHUB_ENV_FILE = 'C:\duong-dan-rieng\coursehub-test.env'
python -m pytest backend/tests/test_enrollment_events.py -v
```

Tệp cấu hình riêng chứa `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
theo mẫu `backend/.env.example`. Có thể dùng các biến môi trường này trực tiếp;
biến đã đặt được ưu tiên hơn tệp dotenv. Không commit mật khẩu.

Mỗi test tạo schema `coursehub_test_<uuid>`, giới hạn search_path vào duy nhất
schema này, dựng schema/seed/migration 001 và index thứ nhất. Các test dùng
PostgreSQL thật và FastAPI TestClient. Dữ liệu thử và identity sequence thuộc
schema riêng; phần finally xóa schema và xác nhận nó không còn tồn tại.

Guard so sánh số dòng, MD5 toàn bộ nội dung từng bảng, metadata cột, index và
giá trị sequence của `current_schema()` nguồn trước/sau. Không INSERT/UPDATE/
DELETE/ALTER bảng nguồn hoặc gọi sequence nguồn. Không chạy cùng lúc với tác vụ
khác đang sửa schema nguồn, vì thay đổi đồng thời cũng làm guard báo sai khác.
Đặt `COURSEHUB_TEST_REPORT` để lưu báo cáo JSON đối chiếu trước/sau.

## Postman: có dữ liệu và không có dữ liệu

Import `postman/CourseHub_Enrollment_Events.postman_collection.json` vào Postman.
Chạy server dữ liệu mẫu từ checkout thử, giữ terminal này mở:

```powershell
python -m backend.tests.postman_demo --port 8011
```

Server dùng chính production app với engine trỏ vào schema dùng một lần. Nó
tạo ba sự kiện cho sinh viên `22000001`, gồm hai sự kiện cùng thời điểm, và không
tạo sự kiện cho `99999999`. Collection có `base_url=http://127.0.0.1:8011`.
Chạy toàn collection bằng Collection Runner. Các request có sẵn assertion cho
dữ liệu, lọc, phân trang, tie-break, biên limit và lỗi 422. Nhấn Ctrl+C trong
terminal server khi xong; context xóa schema và đối chiếu dữ liệu nguồn.

Có thể chạy collection bằng CLI Newman:

```powershell
npx --yes newman@6 run postman/CourseHub_Enrollment_Events.postman_collection.json
```

Để chạy server, Newman và dọn dữ liệu trong một lệnh tự động:

```powershell
npm install --prefix ../coursehub-tools --no-audit --no-fund newman@6
python -m backend.tests.run_postman --newman-cli ../coursehub-tools/node_modules/newman/bin/newman.js --output docs/evidence/postman_events.json
```

Runner đợi server sẵn sàng, chạy collection, yêu cầu shutdown và đợi lifespan
xóa schema. Mã thoát khác 0 nếu assertion, startup hoặc cleanup thất bại.

Collection chỉ gửi GET. Không chạy server bằng `uvicorn backend.app.main:app`
nếu muốn fixture và cơ chế dọn tự động của demo Postman này.

## Ca đúng, ca lỗi và bằng chứng

| Ca | Kết quả |
|---|---|
| Không có bộ lọc | 200, mới nhất trước |
| Lọc riêng student / event_type / kết hợp | 200, đúng mọi điều kiện |
| Cùng occurred_at | ID giảm dần |
| skip và limit | không lặp/mất dòng khi dữ liệu không đổi |
| Không có lịch sử | 200, mảng rỗng |
| limit=1 và limit=100 | hợp lệ |
| limit=0/101/abc, skip=-1/abc | 422 |
| event_type sai, student_id sai độ dài | 422 |
| Chuỗi SQL trong student_id hợp lệ độ dài | được bind như dữ liệu, mảng rỗng |

Workflow `.github/workflows/enrollment-exercises.yml` chạy integration test trên
PostgreSQL 18 dùng một lần, chạy Newman, và lưu bằng chứng trong workflow artifacts.
Output thực tế của lần chạy cục bộ nằm ở `docs/evidence/`; không coi bảng kỳ vọng
là bằng chứng đã PASS. Các PR nối tiếp nhau từ nhánh tuần 4; xem PR từng bài để
biết đúng nhánh nền. Không tự merge các PR khi hoàn thành kiểm thử.
