# Kết quả import Hasaki Demo V1 — 27/11/2026

**Dữ liệu giả lập phục vụ đồ án, không phải số liệu kinh doanh nội bộ Hasaki.**

Đã import thành công qua Migration Patch vào crm.localhost. Sau xác nhận tiếp tục, đối chiếu bảo toàn dữ liệu, seeder độc lập và đầy đủ 37 regression A4.8 đều Passed. Chỉ User.last_active được phép khác; mọi trường User khác vẫn được đối chiếu. Không sửa dữ liệu cũ hoặc demo để làm test Passed. Đây là trạng thái mới nhất ngày 27/11/2026.

## Backup và bảo toàn môi trường

Backup `bench --site crm.localhost backup --with-files` exit 0. Bộ file prefix `20261127_110325-crm_localhost-` tại `/home/frappe/frappe-bench/sites/crm.localhost/private/backups/` gồm site_config_backup.json, database.sql.gz, files.tar, private-files.tar. Đã đọc gzip đến EOF để kiểm tra CRC, database giải nén 11.105.640 bytes; đọc được 402 thành viên archive public và 2 private. SHA256 và kích thước từng file trong `demo_deployment_backup.json`. Không restore, không copy backup/secrets vào repository nhóm.

App đã cài và symlink/mount giữ nguyên. Không new-app/install-app/new-site; không sửa core, Docker, API, Webhook, WordPress Plugin, schema hoặc controller giao dịch. Chỉ bật site config `hasaki_enable_demo_data=1`; hash cấu hình ngoài cờ demo giữ nguyên.

## Kết quả thực chạy theo thứ tự

| Bước | Kết quả |
|---|---|
| 1. Backup đầy đủ, kiểm tra file | Passed |
| 2. Baseline số lượng và hash từng bản ghi/field | Passed; không xuất nội dung cá nhân |
| 3. Dry-run/hook/schema/master/khóa trùng | Passed; patch chưa chạy trước import |
| 4. Bật demo, migrate lần đầu | Passed; patch V1 thực chạy 43,863 giây, Patch Log skipped=0 |
| 5. Số lượng dataset | Passed: 1.200 Order, 3.663 Item |
| 6. Link/tiền/Payment/status/audit | Passed: reconcile toàn bộ khớp JSON |
| 7. Migrate lần hai | Passed; đối chiếu chạy lại chỉ cho phép User.last_active, không thêm/xóa/sửa giao dịch |
| 8. Gọi seeder độc lập | Passed; already_imported, không thêm/xóa/sửa bản ghi |
| 9. Regression A4.8 37 case | Passed 37/37; 13 Lead + 18 WooCommerce + 6 schema/controller |
| 10. Bảo toàn dữ liệu cũ | Passed cả trước/sau regression; chỉ User.last_active đổi, không bỏ qua field User khác |
| 11. Báo cáo/kịch bản/đường dẫn | Đã xuất; người dùng kiểm tra trực tiếp HSK Order/HSK Payment trên Desk và xác nhận hiển thị đúng |

Patch `hasaki_integration.patches.seed_demo_transactions_v1`, Patch Log `4539qjpc07`, creation database `2026-11-27 11:06:01.991848` (timestamp do site trả về; không tự quy đổi timezone). after_migrate gọi cùng seeder sau patch, dữ liệu vẫn đúng 1.200 đơn.

## Đối chiếu số lượng

| DocType | Trước | Sau import | Sau migrate2 |
|---|---:|---:|---:|
| Contact | 108 | 108 | 108 |
| Address | 100 | 100 | 100 |
| User | 6 | 6 | 6 |
| CRM Lead | 99 | 99 | 99 |
| CRM Deal | 30 | 30 | 30 |
| CRM Product | 200 | 200 | 200 |
| HSK Product Category | 14 | 14 | 14 |
| HSK Order | 57 | 1.257 | 1.257 |
| HSK Order Item | 57 | 3.720 | 3.720 |
| HSK Order Status History | 69 | 1.269 | 1.269 |
| HSK Payment | 15 | 1.215 | 1.215 |
| HSK Integration Event | 257 | 257 | 257 |
| Email Queue | 144 | 144 | 144 |
| Notification Log | 140 | 140 | 140 |
| Webhook Request Log | 0 | 0 | 0 |

Sau import, hash mọi bản ghi cũ giữ nguyên. Sau migrate2 không có thêm/xóa bản ghi trong các bảng được theo dõi; duy nhất User.last_active đổi. Bằng chứng `demo_deployment_after_import_comparison.json` và `demo_deployment_after_migrate2_comparison.json`. Số DefaultValue tăng 1 do marker hoàn tất dataset; sau migrate2 giữ nguyên.

## Dữ liệu demo đã xác minh

- Trạng thái Order: Completed 1.020; Cancelled 72; Shipping 48; Processing 36; Pending 24.
- Kênh: WooCommerce 660; POS 480; Manual 60.
- Payment và payment_status: Paid 1.083; Pending 117. Controller tính payment_status, seeder không ép giá trị.
- Tổng giá trị giao dịch: 1.691.883.950 VND; doanh thu Completed + Paid: 1.436.163.950 VND.
- Tất cả Contact Link, Product Link/SKU, quantity, giá bán/giá vốn/chiết khấu, số tiền/ngày/key Payment và trường Order khớp JSON qua reconcile.
- Child table History có đúng 1.200 entry mới tại thời điểm import thật, status khớp Order, changed_by Administrator. 3.622 sự kiện quá khứ giả lập giữ riêng trong status_history.json; không ghi đè audit trail.

## Lỗi kiểm tra trước đây và kết quả xử lý

Hàm compare đã nhận biết User.last_active là telemetry phiên Frappe trong kiểm tra dữ liệu cũ, nhưng điều kiện cuối cho idempotency lại yêu cầu không có bất kỳ field nào thay đổi. Điều kiện đó quá nghiêm ngặt, làm báo lỗi dù giao dịch không đổi. Không có bằng chứng lỗi import hoặc trùng dataset.

Người dùng đã duyệt ngoại lệ đúng User.last_active. Đã sửa riêng bộ so sánh và chạy lại Passed; kiểm tra cả hợp các field trước/sau để không bỏ sót field mới/mất. Test âm xác nhận api_key, modified, enabled, Contact.last_active hoặc HSK Order.status thay đổi đều bị từ chối. Không bỏ qua toàn bộ User và không sửa database để che sai khác. Lỗi so sánh trước đây là Failed đã giải quyết; hiện không có regression Failed. Không reset Patch Log/marker.

## Regression, cleanup và bảo toàn

Chạy nguyên 37 test case A4.8 hiện hữu qua HTTP/controller thật, không sửa API hoặc nội dung test cũ. Verdict được lưu trước cleanup trong demo_deployment_regression_verdict_before_cleanup.json; không thay đổi verdict sau dọn dữ liệu. Chi tiết ở demo_regression_lead.json (13), demo_regression_woocommerce.json (18), demo_regression_schema.json (6).

Runner ghi nhận submission_id/order ID/delivery ID trong bộ nhớ, đối chiếu tập tên trước test và kiểm tra ownership trước khi xóa. Chỉ dọn 43 Integration Event, 2 Payment, 11 Order và 6 Lead mới do lần này tạo qua ORM. on_trash/on_change/after_delete, quyền và Link validation vẫn chạy; không force/ignore_on_trash. Thuộc tính no_feed_on_delete được core hỗ trợ chỉ áp dụng Document test tạm trong cleanup; delete_permanently chỉ cho bản ghi mới đã chứng minh ownership, tránh tạo thêm feed/trash test. Comment/Version/child rows/dynamic references được core dọn đúng chứng từ; không xóa broad prefix a48-test, không đụng test cũ hoặc demo V1.

Sau cleanup, tập tên Order/Payment/Event/Lead và Comment/Version/Deleted Document giống trước regression; không còn bản ghi test của lần này. Site config được khôi phục đúng từng byte sau source WooCommerce test tạm; dùng token đã có, không tạo/rotate credential. Không gọi WooCommerce hoặc cổng thanh toán thật. Naming Series dùng hành vi ORM chuẩn, không reset/sửa thủ công; có thể có khoảng trống mã do test/rollback.

Snapshot trước/sau regression bao gồm toàn bộ demo V1, giao dịch cũ và master/child tables. Không thêm/xóa bản ghi hoặc đổi field nào ngoài User.last_active. Email Queue 144, Notification Log 140, Webhook Request Log 0 giữ nguyên. Bằng chứng demo_deployment_regression_preservation_comparison.json. Đối chiếu baseline trước import ở demo_deployment_after_regression_comparison.json xác nhận dữ liệu cũ nguyên vẹn.

## Cơ chế cập nhật App và cài mới

- **Passed thực tế:** pending post_model_sync patch đã import khi cập nhật App + migrate; migrate lần hai và seeder riêng không trùng; marker complete=true.
- **Passed source/runtime contract:** Frappe runtime đọc đúng after_install/after_migrate; source installer 15.127.1 đánh dấu patch trước after_install; callback trên dataset hiện có trả already_imported. Bằng chứng demo_deployment_lifecycle.json.
- **Passed mô phỏng:** install khi demo tắt rồi bật/migrate vẫn retry; thiếu master làm callback raise và không tạo marker, khắc phục rồi retry được; chuỗi false không bật dataset; patch ở post_model_sync. 16/16 offline/mô phỏng trong demo_offline_results.json.
- **Not Tested end-to-end:** install-app lần đầu trên site mới có master chung. Không tạo/cài lại App hoặc site theo ràng buộc. Không coi source/callback trên App đã cài là chứng minh cài mới thành công.
- **Passed query live không ghi:** mapping từ chối mã Contact và SKU chắc chắn không tồn tại. Không xóa master để dựng lỗi; chỉ dùng đầu vào thử và query thật, không ghi DB (demo_deployment_missing_master.json).

## Mở DocType và giao dịch demo

Đăng nhập site hiện tại; các đường dẫn Desk dưới đây cần phiên đăng nhập. Người dùng đã kiểm tra trực tiếp HSK Order và HSK Payment, xác nhận dữ liệu hiển thị đúng. Đây là xác nhận kiểm thử thủ công của người dùng, không phải test UI tự động:

- Order: `http://crm.localhost:8000/app/hsk-order`
- Payment: `http://crm.localhost:8000/app/hsk-payment`
- Integration Event cũ: `http://crm.localhost:8000/app/hsk-integration-event` (dataset không tạo Event giả).

| Thành viên | Scenario | Order trên site này | Payment |
|---|---|---|---|
| Nghi | NGHI-01: nhiều dòng, demo đổi trả một phần/toàn phần | [HSK-ORD-2026-00119](http://crm.localhost:8000/app/hsk-order/HSK-ORD-2026-00119) | HSK-PAY-2026-00120 |
| Nghi | NGHI-02: đơn cũ | [HSK-ORD-2026-00081](http://crm.localhost:8000/app/hsk-order/HSK-ORD-2026-00081) | HSK-PAY-2026-00082 |
| Trâm | TRAM-01: POS Paid/mua lặp lại | [HSK-ORD-2026-00075](http://crm.localhost:8000/app/hsk-order/HSK-ORD-2026-00075) | HSK-PAY-2026-00076 |
| Trâm | TRAM-02: online không mặc định tích điểm | [HSK-ORD-2026-00153](http://crm.localhost:8000/app/hsk-order/HSK-ORD-2026-00153) | HSK-PAY-2026-00154 |
| Tường | TUONG-01: CLV/RFM/doanh thu | [HSK-ORD-2026-00073](http://crm.localhost:8000/app/hsk-order/HSK-ORD-2026-00073) | HSK-PAY-2026-00074 |
| Nhi | Bảo hành Havatek | Blocked: thiếu SKU Havatek trong master | — |

Mapping đầy đủ mã KH/SKU/khóa ổn định/điều kiện ở `demo_deployment_scenarios.json`; tên Document trên chỉ có giá trị tại site này. Đổi trả tính tại mốc demo 31/10/2026, còn phải đối chiếu chính sách; loyalty_eligible giữ 0 vì chưa có quy tắc được triển khai. Không tạo phiếu bảo hành, Loyalty Transaction, Return/Refund hoặc voucher.

## Passed, Failed và Not Tested còn lại

**Passed:** Migration Patch; migrate2; seeder độc lập; 37/37 regression A4.8; 16/16 offline/mô phỏng; reconcile tất cả đơn/item/payment; mapping thiếu master bằng query live; bảo toàn dữ liệu cũ/demo; cleanup đúng test mới; source/hook/callback lifecycle; build wheel đủ JSON và patch.

**Failed đã xử lý:** phép so sánh đầu tiên quá nghiêm với User.last_active; đã sửa riêng phép so sánh theo xác nhận và chạy lại Passed. Hiện 0/37 regression Failed, 0/16 offline Failed.

**Not Tested:** install-app lần đầu end-to-end; lỗi giữa chừng của seeder full dataset với rollback MariaDB thật (harness Passed và rollback API đã Passed, không tương đương); sửa demo rồi seed giữ sửa đổi trên DB thật (harness Passed, không tự sửa 1.200 đơn demo để làm test); WordPress native/WP-Cron end-to-end mới (37 case là HTTP/controller regression hiện hữu). Không tạo/cài lại App hoặc site, không restore DB để chạy các test này. Desk Passed thủ công theo xác nhận của người dùng.

**Blocker nghiệp vụ:** chưa có Havatek và quy tắc loyalty đã triển khai; không tự tạo master/bảo hành/tích điểm. Scenario liên quan chưa thể nghiệm thu hoàn chỉnh.

Không commit/push/merge; repo nhóm chưa được ghi thay đổi. Fingerprint chi tiết giữ local và ignore khỏi Git. Allowlist DEMO_DATA_FILES.txt gồm 51 file; audit Passed, không khớp bất kỳ secret thật của site/API, không có backup/site config/file môi trường hoặc fingerprint chi tiết; snapshot Contact chỉ chứa custom_customer_id. Kết quả demo_deployment_release_audit.json. Quét secret chỉ đưa ra kết quả/filename, không xuất credential. Source API/Webhook/WordPress Plugin/schema/controller và các test A4.8 gốc không có diff so với Git HEAD; git diff --check Passed.
