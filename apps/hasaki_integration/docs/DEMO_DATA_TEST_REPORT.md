# Kiểm thử Hasaki Transaction Demo Dataset V1.0

**Dữ liệu giả lập phục vụ đồ án, không phải số liệu kinh doanh nội bộ Hasaki.** Ngày 27/11/2026, Asia/Saigon.

**Kết quả cuối sau xác nhận tiếp tục:** Migration Patch thật, migrate2, seeder riêng và 37/37 regression A4.8 Passed. Reconcile 1.200 đơn/3.663 Item/1.200 Payment khớp; dữ liệu cũ và demo giữ nguyên, chỉ chấp nhận User.last_active thay đổi. Không bỏ qua các field User khác. Dữ liệu test mới đã dọn đúng ownership. [Báo cáo triển khai](DEMO_DATA_DEPLOYMENT_REPORT.md) chứa chi tiết và lịch sử lỗi so sánh đã xử lý.

16/16 test offline và transaction harness Passed. Lệnh: `python scripts/report_demo_data.py`; bằng chứng `demo_offline_results.json`. Harness dùng bộ nhớ và mô phỏng controller Payment; không phải bằng chứng ORM/controller/database thật. 37/37 regression riêng chạy HTTP/controller thật: 13 Lead, 18 WooCommerce, 6 schema; bằng chứng demo_regression_lead.json, demo_regression_woocommerce.json, demo_regression_schema.json và demo_deployment_regression.json.

Dry-run trước import Passed: mapping 100 mã KH/200 SKU, không collision, schema/hook/rule hợp lệ, database_writes=0 (demo_dry_run.json). Hiện cờ demo bật, marker complete=true; database có đủ 1.200 Order/3.663 Item/1.200 Payment demo, 1.200 audit entry thời điểm import thật. 3.622 sự kiện nghiệp vụ giả lập giữ trong JSON, không thay audit trail. Tổng giá trị 1.691.883.950 VND; doanh thu Completed+Paid 1.436.163.950 VND. Payment Paid 1.083, Pending 117. Xem demo_deployment_validation.json và demo_final_site_state.json.

| TC | Nội dung | Trạng thái và phạm vi bằng chứng |
|---|---|---|
| TC01 | Schema/Master Data | Passed dry-run đọc metadata/database thật; mapping chính xác |
| TC02 | 1.200 Order | Passed DB thật, reconcile trước/sau regression |
| TC03 | Item/SKU | Passed 3.663 Item, Product Link và SKU từng dòng khớp JSON |
| TC04 | Tổng tiền/chiết khấu | Passed offline và DB từng dòng/đơn; test âm tổng tiền sai được từ chối |
| TC05 | Giá vốn | Passed giá vốn master dương và từng dòng DB khớp snapshot |
| TC06 | Trạng thái | Passed đúng quota/kênh, POS không Shipping; DB khớp JSON |
| TC07 | Payment/payment_status | Passed ORM/controller thật, 1.200 Payment; Paid 1.083/Pending 117; regression xác minh tổng hợp Payment |
| TC08 | Lịch sử | Passed JSON chronology và 1.200 audit entry DB tại import thật; controller giữ audit không bị ghi đè |
| TC09 | Key duy nhất | Passed collision preflight, unique indexes thật và regression concurrent delivery; keys dataset khớp DB |
| TC10 | Import lần hai | Passed seeder độc lập trả already_imported; hash/counts không thay đổi |
| TC11 | Migrate hai lần | Passed hai lệnh thật + đối chiếu, chỉ cho phép User.last_active |
| TC12 | Install App lần đầu | Not Tested end-to-end theo ràng buộc không tạo/cài lại App/site. Passed source/hook registration/callback đã có dataset và harness lifecycle/retry |
| TC13 | Thiếu Contact/Product | Passed mapping lỗi bằng query live với mã không tồn tại, không ghi/xóa master; harness xác minh không tạo marker và retry được |
| TC14 | Rollback | Passed harness seeder và rollback API trong regression; Not Tested seeder full dataset lỗi giữa chừng trên MariaDB thật |
| TC15 | Không đè giao dịch cũ | Passed hash mọi bản ghi cũ trước/sau import, migrate, seeder, regression |
| TC16 | Không đè demo đã sửa | Passed harness; Not Tested sửa demo rồi seed trên DB thật. Demo V1 thực tế giữ nguyên qua mọi test |
| TC17 | Không thông báo/webhook | Passed preflight và runtime: Email Queue/Notification Log/Webhook Request Log không thêm/xóa/sửa |
| TC18 | Bốn thành viên | Passed mapping scenario JSON Nghi/Trâm/Tường; Havatek Blocked; đủ điều kiện tích điểm Blocked; chưa nghiệm thu nghiệp vụ riêng |
| TC19 | Frappe Desk | Passed thủ công theo xác nhận trực tiếp của người dùng: HSK Order và HSK Payment hiển thị đúng; không phải kiểm thử UI tự động |
| TC20 | Regression A4.8 37 case | Passed mới 37/37 qua HTTP/controller thật; đã dọn chính xác dữ liệu test mới |

16 test offline thực chạy gồm 11 test ban đầu và 5 test bổ sung: ngoại lệ chỉ User.last_active (api_key/modified/enabled/DocType khác không được bỏ qua); disabled install rồi bật/migrate retry; master thiếu không tạo marker và retry được; chuỗi false không bật demo; đăng ký lifecycle hook và post_model_sync patch.

Bench chỉ có crm.localhost; người dùng đã duyệt import và regression trên site này. Không tạo site/restore/tạo lại master. test_demo_data_site.py dành riêng cho site test khác chưa được chạy. Regression hiện hữu được bọc bởi demo_regression.run: verdict lưu trước cleanup; chỉ dọn 43 Event, 2 Payment, 11 Order, 6 Lead thuộc lần chạy. Comment/Version/Deleted Document không còn mới; bộ tên và hash cũ giữ nguyên. Không sửa database để làm assertion Passed.

JSON dataset được đọc thành công qua package đang cài trong Bench từ mount Windows, checksum tương thích hai môi trường. Build wheel Passed với flit_core 3.12.0 cài cô lập trong /tmp: đủ 8 JSON nguyên byte và patch, bằng chứng demo_package_results.json. Wheel build trong thư mục tạm, không cài vào site hoặc thay dependencies Bench. Không thay core, schema/controller nghiệp vụ, API Contract, BeautyMatch hoặc App thành viên khác.

Failed lịch sử: bộ so sánh quá nghiêm với User.last_active; đã sửa đúng ngoại lệ được duyệt và chạy lại Passed. Hiện 0 regression Failed và 0 offline Failed. Not Tested còn lại: cài mới end-to-end, seeder full import lỗi/rollback MariaDB, sửa demo rồi seed DB thật và WordPress native/WP-Cron E2E mới. Desk đã được người dùng kiểm tra thủ công và xác nhận đúng. Thiếu Havatek và quy tắc loyalty là blocker nghiệp vụ, không tự bổ sung master hoặc tích điểm để vượt qua.
