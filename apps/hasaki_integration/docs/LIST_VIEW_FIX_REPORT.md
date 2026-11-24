# Báo cáo khắc phục List View A4.8

Ngày kiểm tra: 24/11/2026. Site `crm.localhost`, container `crm-frappe-1`, Frappe `15.127.1`, CRM `1.92.0`.

## Kết luận và cách sửa

Nguyên nhân là **frontend assets cũ không đồng nhất với backend/source Frappe hiện tại**. Backend đã chặn việc yêu cầu đọc `_comments`, source `frappe/public/js/frappe/model/model.js` đã bỏ field này khỏi `std_fields_list`, nhưng bundle đang phục vụ vẫn chứa nó. List View lấy danh sách field từ bundle và gửi field không được phép vào `frappe.desk.reportview.get`.

Đã build lại assets từ đúng source đã cài, rồi clear cache:

```powershell
docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench build --app frappe --production --force
docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench --site crm.localhost clear-cache
```

Không cần migrate vì không thay đổi schema. Không sửa core source, không nâng phiên bản, không thêm Custom Field, không sửa quyền, không reset User Settings. Không cần thêm hook tương thích vào App.

| Bằng chứng | Trước | Sau |
| --- | --- | --- |
| Desk bundle | `desk.bundle.KR73TTV3.js` | `desk.bundle.MLFH6QAY.js` |
| `_comments` trong `std_fields_list` của bundle | Có | Không |
| Backend List query với field lấy từ bundle | 7/7 lỗi | 7/7 Passed |
| SHA256 bundle | `9533c678e86a97d6edd64a6d17dc4572ca08de9076c8403ae6eac92031498c31` | Xem JSON sau sửa |

Bundle mới tải qua HTTP có SHA256 trùng file trên disk; manifest cache trỏ đúng bundle mới; không thiếu file Frappe được manifest tham chiếu. Build có cảnh báo Browserslist cũ và thông báo cleanup CSS không xóa được file; lệnh kết thúc exit code 0. Kiểm tra sau build xác nhận toàn bộ file Frappe trong manifest còn tồn tại. Không cập nhật dependency ngoài phạm vi.

## Tái hiện và traceback

Đã dựng request từ `std_fields_list` của **bundle thực sự đang phục vụ**, gọi trực tiếp backend và endpoint HTTP. Đây là request tái hiện, chưa phải network capture từ trình duyệt người dùng.

Ví dụ field lỗi: `` `tabHSK Order`.`_comments` ``; `filters=[]`, `group_by` là `` `tabHSK Order`.`name` ``, `with_comment_count=1`. DocType dùng cấu trúc tương tự. Như vậy lỗi xuất hiện khi chọn field, không cần Group By theo `_comments`.

```text
frappe/app.py:157 -> frappe.api.handle
frappe/api/v1.py:40 -> frappe.handler.handle
frappe/handler.py:89 -> frappe.call
frappe/desk/reportview.py:33 -> get_form_params
frappe/desk/reportview.py:88 -> validate_args
frappe/desk/reportview.py:96 -> validate_fields
frappe/desk/reportview.py:124 -> raise_invalid_field
frappe/desk/reportview.py:185 -> frappe.throw(..., frappe.DataError)
frappe.exceptions.DataError: Field not permitted in query: tabHSK Order._comments
```

HTTP trước sửa: 417. Traceback đầy đủ cho cả 7 DocType được lưu trong [test_results_list_view_before.json](test_results_list_view_before.json), gồm cả lỗi `tabDocType._comments`. Lần tái hiện HTTP đầu đã dùng phiên Administrator hiện có trong bộ nhớ, không lưu credential. Sau khi kiểm duyệt từ chối mở rộng cách dùng session này sang browser automation, đã bỏ toàn bộ mã lấy session; các lần HTTP sau chỉ dùng API Token tích hợp có sẵn qua xác thực Frappe thông thường.

## Optional fields, metadata và settings

`frappe.model.optional_fields` hiện là `_user_tags`, `_assign`, `_liked_by`, `_seen`; **không có `_comments`**. `reportview.is_standard` sử dụng tập field này khi validate request. Cột vật lý có tồn tại không đồng nghĩa client được phép truy vấn.

Cả 7 bảng đều có cột `_comments`, không có DocField `_comments` và không có Custom Field tương ứng. Không có bản ghi List View Settings cho 7 DocType. Các User Settings hiện có không tham chiếu `_comments`. Nội dung settings và kết quả đối chiếu metadata đã lưu trong JSON trước/sau. Không có căn cứ để sửa database hoặc reset settings.

`DatabaseQuery.set_optional_columns` loại các optional columns không tồn tại; cơ chế này không cấp quyền cho `_comments`. Backend tự xử lý cache `_comments` khi cần đếm Comment, rồi `add_comment_count` loại raw cache và trả `_comment_count`. Kiểm tra HTTP xác nhận vẫn trả `_comment_count`, không trả `_comments`.

## Đối chiếu issue #44499

[Issue #44499](https://github.com/frappe/frappe/issues/44499) mô tả Report View có Group By đã lưu trên optional field; có thêm phản ánh lỗi List View trên v15. Tuy nhiên phải đối chiếu request và traceback để phân biệt nguyên nhân.

[PR #44601](https://github.com/frappe/frappe/pull/44601) được merge vào `develop`, sửa frontend để bỏ Group By đã lưu trên field không thể query; server tiếp tục chặn `_comments`. Diff sửa `base_list.js`, `group_by.js` và bổ sung Playwright test. Source v15.127.1 tại máy chưa có helper `is_queryable_field` và phần filter saved Group By như PR này. Không thể kết luận cứ dùng v15.127.1 là đã có toàn bộ PR đó.

Source local đã có commit `364eea7ea675f2fc86aa10cde49685b4a3a0c832`, `fix: stop exposing _comments through list queries (backport #42927)`: loại `_comments` ở Python và JavaScript. Vì source đã đúng mà assets còn cũ, build lại giải quyết nguyên nhân thực tế. Không cherry-pick PR #44601 hoặc sửa `_validate_group_by_field`; không áp dụng đề xuất nới whitelist trong issue. Trường hợp saved Report Group By riêng biệt chưa được tạo mới để test và không thuộc lỗi hiện tại.

## Kiểm thử sau sửa

Backend chạy `reportview.get` với user Administrator trong Bench; kiểm tra quyền gốc vẫn hoạt động, không dùng `ignore_permissions`.

| List View | Backend Administrator | HTTP bằng Sales User hiện có |
| --- | --- | --- |
| DocType | Passed | 403 PermissionError, đúng quyền |
| HSK Order | Passed | 200 |
| HSK Payment | Passed | 200 |
| HSK Integration Event | Passed | 403 PermissionError, đúng quyền |
| CRM Lead | Passed | 200 |
| CRM Deal | Passed | 200 |
| Contact | Passed | 200 |

[test_results_list_view_after.json](test_results_list_view_after.json) ghi request, metadata, settings, row count, hash assets và kết quả thực tế. Các request này dùng field chuẩn từ bundle; chưa bao gồm mọi tổ hợp filter, cột tùy chỉnh hoặc Report View.

Kiểm tra bổ sung qua HTTP: `_comments` trong fields, filters, or_filters, biểu thức `coalesce` và một field không tồn tại đều bị chặn 417. `with_comment_count=1` vẫn trả 200 cùng `_comment_count`. Query chỉ dùng `_comments` làm group_by hoặc order_by trả 200 với core hiện tại, không trả raw `_comments`; đã ghi là **Observed**, không ghi nhầm thành test chứng minh chúng bị chặn. Không sửa hành vi core này trong phạm vi khắc phục assets.

Đã chạy lại toàn bộ **37 test A4.8**, không sửa test để ép Passed:

| Suite | Số test | Thời điểm ghi nhận giờ site | Kết quả |
| --- | --- | --- | --- |
| LeadHTTPTests | 13 | 2026-11-24 12:32:29.169578 | Passed |
| WooHTTPTests | 18 | 2026-11-24 12:32:45.706430 | Passed |
| SchemaTests | 6 | 2026-11-24 12:33:21.065534 | Passed |

Chi tiết từng test trong [TEST_REPORT.md](TEST_REPORT.md) và ba JSON `test_results_lead.json`, `test_results_woocommerce.json`, `test_results_schema.json`. Cả ba suite xác nhận Master business data unchanged = true, không có thay đổi field master. HTTP suites tạo thêm giao dịch test theo cơ chế sẵn có; không xóa dữ liệu nền hoặc chứng từ cũ. Không chạy lại WP-Cron/E2E WordPress vì lần này không đổi code tích hợp; kết quả các lần trước không được tính là lần chạy mới.

## Giới hạn nghiệm thu giao diện

Chưa kiểm thử thao tác và render của 7 trang trong browser đăng nhập, chưa chụp ảnh và chưa thu network request từ UI thật. Kiểm duyệt tự động đã từ chối cách lấy session Administrator từ database rồi đưa vào Edge; lý do là sử dụng thông tin phiên ngoài luồng xác thực phù hợp. Script browser đó đã được loại bỏ, không thực thi qua đường khác. Cần phiên kiểm thử qua luồng đăng nhập thông thường được người dùng cấp để hoàn tất phần UI. Kết quả backend/HTTP ở trên không được coi là 7 trang UI đã nghiệm thu đầy đủ.

Sau build, tab Desk đang mở cần tải lại toàn bộ trang để nạp bundle mới (Ctrl+Shift+R). Trong Network kiểm tra URL `desk.bundle.MLFH6QAY.js`, rồi mở lần lượt 7 route và xác nhận `frappe.desk.reportview.get` không còn gửi `_comments`. Đối với DocType/Integration Event, dùng tài khoản có quyền hiện có; không thêm role để vượt bài test.

## File thay đổi và phòng tránh tái diễn

- Thêm `hasaki_integration/list_view_audit.py`: script Bench chẩn đoán, không whitelist thành API; đọc metadata/settings, tái hiện query, đối chiếu hash asset HTTP/disk và kiểm tra quyền/bảo mật.
- Thêm báo cáo này cùng JSON List View trước/sau; cập nhật tài liệu bàn giao/test và JSON kết quả 37 test.
- Cập nhật `scripts/build_handover_docs.py` để giữ liên kết tới báo cáo sửa lỗi khi sinh lại tài liệu.
- Runtime artifacts thay đổi: Frappe `public/dist`, `sites/assets/assets.json`, assets RTL và translations do lệnh build chuẩn sinh ra; không phải chỉnh sửa core source bằng tay. Bench có relink assets của các App tới cùng đường dẫn; chỉ build Frappe. Entry bundle BeautyMatch giữ nguyên `beautymatch_portal.bundle.4TS4P4XQ.js`.

Frappe HEAD giữ nguyên `0f31ab048faa89330ab4f30c1a113c7606ca4dec`, CRM HEAD giữ nguyên `638bf3db23e7142870819a213368e028866b79b1`; `git status --short` của hai core repo đều rỗng sau xử lý. Không push GitHub.

Khi thay source/version Frappe, phải build assets từ cùng revision trước nghiệm thu; clear-cache không biên dịch lại JavaScript. Không copy bundle của bản cũ sang source mới. Có thể chạy lại:

```powershell
docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench --site crm.localhost execute hasaki_integration.list_view_audit.run_after
```

Script dùng API Token tích hợp hiện có, không tạo credential; kết quả HTTP 403 của tài khoản thiếu quyền là kỳ vọng. Source test hardcode môi trường local, cần review trước khi tái sử dụng ở site khác. Không đặt secrets vào báo cáo hoặc ảnh minh chứng.
