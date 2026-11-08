# Bài 2: Kiểm thử rollback nhiều bảng

Issue: [#5](https://github.com/NMinZ17/coursehub-demo/issues/5).

## Mục tiêu và phạm vi

Chứng minh một transaction bảo đảm tính nguyên tử khi ghi hai bảng: câu
`INSERT enrollments` đã thực hiện thành công, nhưng câu
`INSERT enrollment_events` tiếp theo vi phạm CHECK `ck_enrollment_events_type`.
Kết quả cần quan sát là cả số dòng và nội dung hai bảng sau request lỗi giống
trước request.

Ứng dụng demo nằm riêng trong `backend/tests/rollback_demo.py`. Factory
`create_demo_app(test_engine)` chỉ được kiểm thử bằng một engine trỏ vào schema
thử dùng một lần. `backend/app/main.py` không import hay đăng ký router demo.
Không chạy ứng dụng demo bằng cấu hình production, không gắn route này vào
production app và không triển khai endpoint demo lên máy chủ.

## Vì sao lỗi này chứng minh rollback

Model demo cố ý cho `event_type` là chuỗi. Giá trị `INVALID` đi qua kiểm tra đầu
vào của API và chạm tới PostgreSQL. Nếu dùng `Literal["CREATED", "CANCELLED"]`
ở đây, FastAPI sẽ trả 422 trước khi ghi CSDL, nên chưa chứng minh được rollback.

Hai lệnh INSERT dùng cùng `connection` trong `with test_engine.begin()`.
Handler `except IntegrityError` đặt **ngoài** khối `with`, do đó transaction được
rollback trước khi trả HTTP 409. Handler chỉ nhận đúng SQLSTATE `23514` và tên
constraint `ck_enrollment_events_type`; lỗi khóa ngoại hay trùng khóa không bị
nhận nhầm là kết quả kiểm thử thành công.

Test gắn listener SQLAlchemy để xác nhận câu INSERT vào `enrollments` hoàn tất
trước khi câu INSERT vào `enrollment_events` được thử. Sau response, test mở
kết nối riêng để đọc dữ liệu đã commit, thay vì chỉ đọc trong transaction cũ.

## Chạy kiểm thử

Cài dependencies phát triển và cấu hình kết nối PostgreSQL theo hướng dẫn
chung của bài 1. Tài khoản kiểm thử cần quyền tạo và xóa schema thử. Chạy từ
gốc bản làm việc chứa PR:

```powershell
python -m pytest backend/tests/test_rollback.py -v
```

Fixture `db_engine` dựng schema PostgreSQL riêng với schema, seed và migration
001. Sinh viên `22000004` chưa đăng ký lớp `WEB-02`, vì vậy INSERT đầu tiên có
thể thành công. Mỗi test nhận môi trường mới và không phụ thuộc thứ tự chạy.

## Ca đúng và ca lỗi

| Ca | Đầu vào/kiểm tra | Kết quả cần đạt |
|---|---|---|
| Ghi thành công | Sinh viên `22000004`, lớp `WEB-02`, `event_type=CREATED` | HTTP 201; mỗi bảng tăng một dòng; JOIN tìm thấy đúng cặp sinh viên/lớp và sự kiện CREATED |
| Lỗi ở INSERT thứ hai | Cùng cặp sinh viên/lớp, `event_type=INVALID` | INSERT enrollments đã hoàn tất; PostgreSQL báo CHECK `23514`; HTTP 409; số dòng và SHA-256 nội dung của hai bảng không đổi |
| Cách ly production | POST `/demo/enrollments` trên production app | HTTP 404; OpenAPI production không chứa đường dẫn demo |

Request lỗi trong test tương đương:

```http
POST /demo/enrollments
Content-Type: application/json

{
  "student_id": "22000004",
  "class_section_id": "WEB-02",
  "event_type": "INVALID"
}
```

Response 409 của ứng dụng thử có trường `detail.constraint` bằng
`ck_enrollment_events_type` và `detail.sqlstate` bằng `23514`. Đây là thông tin
chẩn đoán của demo kiểm thử, không phải hợp đồng API production.

## Khôi phục dữ liệu sau kiểm thử

Ca lỗi tự rollback các dòng vừa ghi. Ca đúng cố ý commit để kiểm tra khả năng
ghi thật; teardown của fixture xóa toàn bộ schema thử và sequence riêng của nó.
Schema gốc không bị INSERT, UPDATE, DELETE hay ALTER. Hạ tầng kiểm thử đối
chiếu trạng thái gốc trước/sau và xác nhận không còn schema thử.

PostgreSQL không rollback giá trị sequence sau `nextval()`, vì vậy không dùng
ID liên tục làm tiêu chí kiểm thử. Sequence ở schema gốc không được gọi; sequence
trong schema dùng một lần được xóa cùng schema. Cách này giữ nguyên dữ liệu và
sequence gốc mà không cần đặt lại bộ đếm đang được ứng dụng khác sử dụng.

## Bằng chứng đưa vào Pull Request

Đính kèm output pytest thực tế cho ba ca trên. Không ghi “PASS” trước khi chạy.
Mô tả PR cần nêu rõ route demo chỉ tồn tại trong ứng dụng kiểm thử, hai bảng được
đọc bằng kết nối riêng sau request và dữ liệu gốc được đối chiếu sau teardown.
