# Bài 4 — Migration 002 thêm ghi chú sự kiện

Issue: [#7](https://github.com/NMinZ17/coursehub-demo/issues/7).

Migration `002_add_enrollment_event_note.sql` thêm cột `note VARCHAR(200)` cho
`enrollment_events`. Cột cho phép `NULL`; các sự kiện đã tồn tại giữ nguyên ID,
sinh viên, lớp, loại sự kiện, nguồn, dataset và thời điểm. Ghi chú ban đầu là
`NULL`. API hiện chọn các cột tường minh nên tiếp tục hoạt động trước và sau 002.

## Áp dụng và rollback

Chỉ thực hiện sau migration 001. Sao lưu CSDL đích trước khi áp dụng. Kiểm tra
đúng database và schema; dùng một phiên `psql` có `search_path` phù hợp.

```sql
SELECT current_database(), current_schema();
SELECT version FROM schema_migrations ORDER BY version;
```

Từ thư mục gốc repository, chạy thủ công trên CSDL thử riêng:

```powershell
psql -h 127.0.0.1 -U coursehub_user -d coursehub_test -v ON_ERROR_STOP=1 -f database/migrations/002_add_enrollment_event_note.sql
```

Không đưa mật khẩu vào lệnh hoặc commit `.env`. Tệp SQL có `BEGIN`/`COMMIT`:
thay đổi schema và thêm version `002` cùng thành công hoặc cùng rollback. Không
dùng `IF NOT EXISTS` để che việc chạy trùng hay trạng thái migration lệch nhau.

Rollback thủ công, sau khi xuất các ghi chú cần giữ:

```powershell
psql -h 127.0.0.1 -U coursehub_user -d coursehub_test -v ON_ERROR_STOP=1 -f database/migrations/002_add_enrollment_event_note_rollback.sql
```

**Rollback làm mất toàn bộ nội dung `note`.** `DROP COLUMN` giữ các dòng sự kiện
và các cột cũ, nhưng xóa dữ liệu ghi chú. Chạy lại migration 002 chỉ tạo lại cột
với giá trị `NULL`, không khôi phục ghi chú. Muốn phục hồi nội dung phải dùng bản
sao lưu. Không sử dụng rollback này khi chưa chấp nhận việc mất ghi chú.

## Kiểm thử tự động trên dữ liệu có sẵn

```powershell
python -m pytest backend/tests/test_migration_002.py -v
```

Nếu dùng cấu hình từ tệp khác, đặt `COURSEHUB_ENV_FILE` theo hướng dẫn kiểm thử
chung. Bộ kiểm thử dùng PostgreSQL thật trong schema thử riêng do fixture
`db_engine` tạo. Trước mỗi migration, kiểm thử commit ba sự kiện có đủ khóa ngoại
hợp lệ; vì vậy không chỉ kiểm tra trên bảng rỗng. So sánh toàn bộ giá trị của
bảy cột cũ theo ID, thay vì chỉ so sánh số dòng.

| Ca | Kết quả được kiểm tra |
|---|---|
| Áp dụng 002 trên dữ liệu có sẵn | Mọi giá trị cũ giữ nguyên; cột nullable, giới hạn 200; đúng một version 002 |
| Dữ liệu cũ sau áp dụng | Tất cả ghi chú mới đều `NULL` |
| 200 ký tự ASCII | Lưu đủ, không bị cắt |
| 200 ký tự Unicode `ộ` | Lưu đủ 200 ký tự; kiểm tra giới hạn ký tự thay vì số byte |
| `NULL` | Được chấp nhận |
| 201 ký tự Unicode | PostgreSQL từ chối với SQLSTATE `22001`; dữ liệu không đổi |
| Chạy trùng migration tiến | Lỗi `42701`; không thêm bản ghi version hoặc đổi dữ liệu |
| INSERT version 002 bị trùng sau ALTER thành công | Lỗi `23505`; cột vừa thêm cũng rollback, chứng minh tính nguyên tử |
| Rollback khi đã có ghi chú | Xóa cột và version 002; mọi giá trị cũ giữ nguyên |
| Áp dụng lại sau rollback | Ghi chú cũ không trở lại, mọi note là `NULL` |
| Chạy trùng rollback | Lỗi `42703`; các dòng và migration khác giữ nguyên |

Các tệp SQL thật được chạy nguyên nội dung, kể cả `BEGIN`/`COMMIT`; sau một ca
lỗi, helper gửi `ROLLBACK` trước khi trả kết nối vào pool. Ca 201 ký tự dùng
`UPDATE ... SET note = :note`, không ép kiểu sang `VARCHAR(200)` vì phép cast
tường minh có thể cắt chuỗi và làm sai ý nghĩa kiểm thử.

## Khôi phục sau kiểm thử

Fixture xóa toàn bộ schema thử trong phần `finally`, gồm bảng, identity sequence,
index và registry migration thử. Vì thế dữ liệu, schema và sequence hiện tại của
CSDL nguồn không bị thay đổi. Kiểm tra bảo toàn nguồn của bộ kiểm thử chung phải
thành công trước khi ghi kết quả PASS. Nếu chạy thủ công trong `coursehub_test`,
khôi phục bản sao lưu ban đầu sau khi lưu bằng chứng; chỉ DELETE fixture không
đặt lại sequence PostgreSQL.

## Nội dung PR

- Liên kết `Closes #7` và nêu nhánh nền của bài trước.
- Đính kèm tệp migration tiến, rollback và bộ kiểm thử trên.
- Ghi kết quả chạy thực tế cùng thời điểm, không thay kết quả bằng bảng kỳ vọng.
- Nêu rõ migration tiến giữ dữ liệu cũ; rollback xóa mọi dữ liệu trong `note`.
