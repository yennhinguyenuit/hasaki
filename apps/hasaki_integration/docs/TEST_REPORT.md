# TEST REPORT — A4.8

Ngày tổng kết: 24/11/2026, múi giờ nghiệp vụ Asia/Ho_Chi_Minh. Báo cáo dựa trên các kết quả đã lưu, không coi nội dung test source đơn thuần là minh chứng chạy thành công.

## 1. Tổng quan kết quả

| Bộ kiểm thử | Số test case | Kết quả | Minh chứng |
| --- | --- | --- | --- |
| LeadHTTPTests | 13 | Passed | test_results_lead.json |
| WooHTTPTests | 18 | Passed | test_results_woocommerce.json |
| SchemaTests | 6 | Passed | test_results_schema.json |
| Tổng test case tự động chính | **37** | **37 Passed, 0 Failed** | Ba JSON phía trên |

HTTP tests chạy vào server thật port 8000 của crm.localhost, có đọc database để xác nhận. SchemaTests chạy controller/metadata MariaDB thật rồi rollback giao dịch test. Các bài WordPress E2E, PHP adapter và WP-Cron bên dưới là minh chứng bổ sung, không cộng lại vào con số 37.


## 2. Lead API — 13 test case

Lần chạy ghi nhận: **2026-11-24 11:51:43.587435** (giờ site). Source: `hasaki_integration/tests/test_integration_http.py`.


### TC01 — test_concurrent_duplicate_submission

- Thao tác: Gửi 4 POST đồng thời cùng submission_id và payload.
- Kỳ vọng và kiểm tra thực tế: Cả 4 trả 200; một Lead, một lần idempotent=false.
- Kết quả: **Passed**.


### TC02 — test_consent_requires_boolean

- Thao tác: Gửi consent lần lượt là chuỗi true, số 1, chuỗi 1 và null.
- Kỳ vọng và kiểm tra thực tế: Tất cả trả 400; chỉ JSON boolean true được nhận.
- Kết quả: **Passed**.


### TC03 — test_duplicate_submission_returns_original_lead

- Thao tác: POST hợp lệ hai lần với cùng submission_id.
- Kỳ vọng và kiểm tra thực tế: Lần sau 200, idempotent=true và cùng data.lead/data.event.
- Kết quả: **Passed**.


### TC04 — test_false_consent_rejected_and_logged

- Thao tác: Gửi consent=false với submission_id hợp lệ.
- Kỳ vọng và kiểm tra thực tế: 400 VALIDATION_ERROR; Event Failed, không có Lead tham chiếu.
- Kết quả: **Passed**.


### TC05 — test_get_is_not_allowed

- Thao tác: Gọi GET vào receive_lead.
- Kỳ vọng và kiểm tra thực tế: Bị từ chối 403 hoặc 405 theo Frappe; không được dùng GET để tạo Lead.
- Kết quả: **Passed**.


### TC06 — test_html_message_is_safe

- Thao tác: Gửi message chứa script và thẻ HTML.
- Kỳ vọng và kiểm tra thực tế: Comment không chứa thẻ script thực thi; nội dung tư vấn còn được lưu.
- Kết quả: **Passed**.


### TC07 — test_invalid_email_and_phone

- Thao tác: Thử email sai, phone chứa chữ và phone quá ngắn.
- Kỳ vọng và kiểm tra thực tế: Các request trả 400.
- Kết quả: **Passed**.


### TC08 — test_invalid_token_rejected_without_event

- Thao tác: Gửi API Token không hợp lệ.
- Kỳ vọng và kiểm tra thực tế: 401 UNAUTHORIZED; không có Integration Event cho submission.
- Kết quả: **Passed**.


### TC09 — test_missing_fields_do_not_create_lead

- Thao tác: Bỏ lần lượt submission_id, first_name, phone, message.
- Kỳ vọng và kiểm tra thực tế: 400; tổng số Lead không tăng.
- Kết quả: **Passed**.


### TC10 — test_no_token_rejected_without_event

- Thao tác: Không gửi Authorization.
- Kỳ vọng và kiểm tra thực tế: 401 UNAUTHORIZED; không có Event.
- Kết quả: **Passed**.


### TC11 — test_optional_fields_can_be_omitted

- Thao tác: Không gửi last_name và email.
- Kỳ vọng và kiểm tra thực tế: 200 và ok=true.
- Kết quả: **Passed**.


### TC12 — test_reused_key_with_different_payload_conflicts

- Thao tác: Sau request thành công, đổi message nhưng giữ submission_id.
- Kỳ vọng và kiểm tra thực tế: 409 CONFLICT; không tạo Lead thứ hai.
- Kết quả: **Passed**.


### TC13 — test_valid_lead_mapping_and_comment

- Thao tác: Gửi đủ 7 trường hợp lệ và đọc trực tiếp database.
- Kỳ vọng và kiểm tra thực tế: Tên/email/mobile_no/source đúng; đúng một Comment; Event Processed liên kết đúng Lead.
- Kết quả: **Passed**.


## 3. WooCommerce API — 18 test case

Lần chạy ghi nhận: **2026-11-24 11:51:39.857263** (giờ site). Source: `hasaki_integration/tests/test_integration_http.py`.


### TC14 — test_activation_probe_writes_no_business_data

- Thao tác: POST form-encoded webhook_id dương không có chữ ký.
- Kỳ vọng và kiểm tra thực tế: 200 WEBHOOK_PROBE; không tạo Order.
- Kết quả: **Passed**.


### TC15 — test_bad_signature_has_no_event_or_order

- Thao tác: Gửi payload với chữ ký HMAC sai.
- Kỳ vọng và kiểm tra thực tế: 401 INVALID_SIGNATURE; không có Order hoặc Event.
- Kết quả: **Passed**.


### TC16 — test_concurrent_duplicate_delivery

- Thao tác: Gửi 4 webhook đồng thời cùng delivery/payload.
- Kỳ vọng và kiểm tra thực tế: 200; cùng một Order và chỉ một lần xử lý mới.
- Kết quả: **Passed**.


### TC17 — test_confirmed_payment_created_once

- Thao tác: Gửi date_paid_gmt hợp lệ, phát lại và gửi phiên bản mới.
- Kỳ vọng và kiểm tra thực tế: Chỉ một Payment Paid; amount/paid_at đúng, Order.payment_status=Paid.
- Kết quả: **Passed**.


### TC18 — test_create_order_items_cost_snapshot_and_guest

- Thao tác: Gửi order.created có SKU hiện hữu và khách chưa khớp.
- Kỳ vọng và kiểm tra thực tế: Order/Item đúng, snapshot cost đúng, GMT chuyển +07, guest được lưu, chưa có Payment.
- Kết quả: **Passed**.


### TC19 — test_duplicate_delivery_returns_same_order

- Thao tác: Gửi lại cùng delivery/payload.
- Kỳ vọng và kiểm tra thực tế: idempotent=true; cùng Order, không thêm status history.
- Kết quả: **Passed**.


### TC20 — test_duplicate_line_ids_rejected

- Thao tác: Hai line_items dùng cùng id.
- Kỳ vọng và kiểm tra thực tế: 400 và không tạo Order.
- Kết quả: **Passed**.


### TC21 — test_equal_timestamp_different_payload_conflicts

- Thao tác: Giữ date_modified_gmt nhưng đổi status/payload.
- Kỳ vọng và kiểm tra thực tế: 409; Order giữ status ban đầu.
- Kết quả: **Passed**.


### TC22 — test_invalid_money_and_currency_rejected

- Thao tác: Thử NaN, Infinity, tiền âm và currency USD.
- Kỳ vọng và kiểm tra thực tế: 400; chỉ tiền hữu hạn không âm, currency VND được nhận.
- Kết quả: **Passed**.


### TC23 — test_invalid_second_line_rolls_back_entire_order

- Thao tác: Dòng đầu hợp lệ, dòng hai có SKU không tồn tại.
- Kỳ vọng và kiểm tra thực tế: 422; toàn Order được rollback, không lưu dở dòng đầu.
- Kết quả: **Passed**.


### TC24 — test_missing_order_update_does_not_create_order

- Thao tác: order.updated cho ID chưa có Order.
- Kỳ vọng và kiểm tra thực tế: 409; không upsert Order thiếu.
- Kết quả: **Passed**.


### TC25 — test_payment_conflict_rolls_back_order_and_history

- Thao tác: Sau Paid, thay amount tổng và status trong phiên bản mới.
- Kỳ vọng và kiểm tra thực tế: 409; grand_total/status/history cũ và đúng một Payment được giữ.
- Kết quả: **Passed**.


### TC26 — test_same_native_delivery_id_can_deliver_different_orders

- Thao tác: Hai Order khác nhau dùng cùng Delivery-ID.
- Kỳ vọng và kiểm tra thực tế: Cả hai 200 và có hai mã Order khác nhau.
- Kết quả: **Passed**.


### TC27 — test_same_native_delivery_id_can_deliver_newer_order_version

- Thao tác: Cùng Delivery-ID nhưng gửi topic/version cập nhật mới hơn.
- Kỳ vọng và kiểm tra thực tế: 200; cập nhật cùng Order sang Processing.
- Kết quả: **Passed**.


### TC28 — test_stale_event_cannot_overwrite_order

- Thao tác: Sau phiên bản mới, gửi phiên bản có date_modified_gmt cũ.
- Kỳ vọng và kiểm tra thực tế: 200 với ignored_stale=true; status/history hiện tại không bị ghi đè.
- Kết quả: **Passed**.


### TC29 — test_unknown_sku_fails_without_product_creation

- Thao tác: Gửi SKU chưa có trong CRM Product.
- Kỳ vọng và kiểm tra thực tế: 422 SKU_NOT_FOUND, Event Failed, không có Order; master hash được kiểm tra ở cuối suite.
- Kết quả: **Passed**.


### TC30 — test_unknown_source_rejected

- Thao tác: X-WC-Webhook-Source không được cấu hình.
- Kỳ vọng và kiểm tra thực tế: 401 INVALID_SIGNATURE và không có Order.
- Kết quả: **Passed**.


### TC31 — test_update_existing_order_and_history_without_automatic_payment

- Thao tác: Tạo Pending rồi gửi Processing mới hơn, không có date_paid_gmt.
- Kỳ vọng và kiểm tra thực tế: Cùng một Order, thêm đúng lịch sử Processing; Payment vẫn chưa có và payment_status=Pending.
- Kết quả: **Passed**.


## 4. Schema/controller — 6 test case

Lần chạy ghi nhận: **2026-11-24 11:51:45.566977** (giờ site). Source: `hasaki_integration/tests/test_schema.py`.


### TC32 — test_five_doctypes_match_source

- Thao tác: So sánh metadata site với cả 5 JSON schema.
- Kỳ vọng và kiểm tra thực tế: Module/custom/istable và fieldtype/options/unique/reqd khớp.
- Kết quả: **Passed**.


### TC33 — test_guest_permissions_and_event_read_only

- Thao tác: Kiểm tra Guest CRUD và quyền Event của manager hiện hữu.
- Kỳ vọng và kiểm tra thực tế: Guest bị từ chối; manager đọc được Event nhưng không được tạo Event.
- Kết quả: **Passed**.


### TC34 — test_history_cannot_be_overwritten_from_resource_api_data

- Thao tác: Xóa status_history trong dữ liệu Document rồi đổi status và save.
- Kỳ vọng và kiểm tra thực tế: Controller phục hồi dòng cũ và append dòng mới. Đây là test controller, không phải một request Resource API qua HTTP.
- Kết quả: **Passed**.


### TC35 — test_manual_orders_allow_multiple_empty_integration_keys

- Thao tác: Tạo hai Order Manual có integration_key trống.
- Kỳ vọng và kiểm tra thực tế: Hai Order khác tên, cùng được chấp nhận với key null.
- Kết quả: **Passed**.


### TC36 — test_multiple_payments_aggregate_and_paid_at_required

- Thao tác: Order 100.000, thêm Payment Paid 40.000 rồi 60.000; thử Paid thiếu paid_at.
- Kỳ vọng và kiểm tra thực tế: Order lần lượt Pending rồi Paid; Paid thiếu paid_at bị từ chối.
- Kết quả: **Passed**.


### TC37 — test_unique_indexes_exist_in_database

- Thao tác: SHOW INDEX trên Order, Payment, Integration Event.
- Kỳ vọng và kiểm tra thực tế: Có unique index tương ứng integration_key, payment_integration_key, idempotency_key.
- Kết quả: **Passed**.


## 5. Kiểm thử tích hợp website thật

| Bài kiểm tra | Thực tế ghi nhận | Kết quả / minh chứng |
| --- | --- | --- |
| Form công khai → PHP WordPress → Lead API | Form/nonce hiện trên site; POST redirect 303 sent; tiếng Việt, mobile_no/source/Comment đúng | Passed — [test_results_wordpress_e2e.json](test_results_wordpress_e2e.json), Lead CRM-LEAD-2026-00130 |
| Gửi lại cùng form | Cùng submission_id chỉ một Event, một Lead và một Comment | Passed — cùng báo cáo form |
| Form không consent | Redirect error, không gọi CRM tạo Event | Passed — cùng báo cáo form |
| Native WC_Webhook + Action Scheduler theo đơn test | Order WordPress 1943 → HSK-ORD-2026-00041; Payment HSK-PAY-2026-00042; replay không trùng | Passed — [test_results_woocommerce_e2e.json](test_results_woocommerce_e2e.json) |
| SKU toàn catalog | 200 SKU WordPress khớp 200 CRM Product, thiếu 0, trùng 0 | Passed — [wordpress_catalog_compatibility.json](wordpress_catalog_compatibility.json) |
| Giữ nguyên website | Hash bản ghi sản phẩm, metadata sản phẩm, file theme và theme đang chọn giữ nguyên; plugin cũ còn hoạt động | Passed — [wordpress_preservation.json](wordpress_preservation.json) |
| PHP adapter bằng API doubles | Parse message, token backend, không follow redirect, payload JSON, retry nguyên body, conflict, consent | Passed qua php scripts/test_wordpress_bridge.php; không coi đây là WordPress E2E |
| Python/PHP/JSON/diff | compileall, PHP lint trên XAMPP, đọc JSON, git diff --check | Passed ở các lượt kiểm tra đã thực hiện; Ruff chưa có trong Bench |

Thử native đầu tiên có update tới trước create và nhận 409; sau create thành công, giao lại đã đạt. Đây là hành vi đã quan sát và được ghi trong báo cáo E2E, không xóa Event lỗi để che dấu lịch sử. Payment dùng date_paid_gmt test, không thu tiền thật.

## 6. WP-Cron tự động, không chạy action thủ công

Kết quả **Passed**, quan sát tổng cộng **35.88 giây**. Đơn WordPress **1944** → **HSK-ORD-2026-00056**, Payment test **HSK-PAY-2026-00057**.

Phương pháp: tạo Order test bằng WooCommerce API nội bộ; để shutdown tự enqueue webhook. Sau đó chỉ HTTP GET trang chủ như người dùng bình thường. Không gọi process_action, không gọi runner->run, không bấm Run, không gọi trực tiếp wp-cron.php. Mode cron-create/cron-update của script chỉ tạo/cập nhật giao dịch test; các guard email/stock/sales chỉ tồn tại trong tiến trình CLI đó.

Minh chứng [test_results_wp_cron.json](test_results_wp_cron.json):

- Site không bật DISABLE_WP_CRON; action_scheduler_run_queue được lập lịch every_minute, interval 60.
- Action 1985 order.created: started via WP Cron lúc 04:59:29 UTC = 11:59:29 giờ Việt Nam, complete lúc 11:59:30.
- Action 1986 order.updated: started/complete via WP Cron lúc 11:59:30 giờ Việt Nam.
- Action 1988 order.updated sau cập nhật: started lúc 11:59:52, complete lúc 11:59:53 giờ Việt Nam.
- Apache access log có POST loopback wp-cron.php HTTP 200 lúc 11:59:27 và 11:59:50. Đây là request tự sinh từ WordPress, không phải lệnh gọi trực tiếp của bài test.
- CRM có đúng một Order, đúng một Payment và các Event của đơn test là Processed. Product/theme hash được kiểm tra lại sau bài test vẫn khớp backup.

Tham số inspector_only_disable_wp_cron=true trong JSON chỉ áp dụng tiến trình CLI **đọc** trạng thái, không phải cấu hình website. Nó tránh làm chính lệnh inspect trở thành tác nhân chạy cron. Không thay wp-config để bật/tắt cron trong bài này.

WP-Cron phụ thuộc lượt truy cập hoặc bộ lịch ngoài. Kết quả này xác nhận chức năng tự động trong cửa sổ quan sát ngắn; không phải bảo đảm độ trễ 60 giây hoặc hoạt động khi không có traffic.

## 7. Bảo toàn dữ liệu

Các suite chính chụp hash từng bảng/từng field cho Contact, CRM Product, HSK Product Category, User, Role, CRM Lead Source. Kết quả gần nhất đều master_business_data_unchanged=true; không ghi nhận khác biệt field trong ba lượt suite đó. User.last_active do Frappe tự cập nhật được theo dõi riêng nếu phát sinh.

Mốc master: Contact 108, CRM Product 200, HSK Product Category 14, User 6, Role 28, CRM Lead Source 8. Việc cấp token cho user hiện hữu là cấu hình tích hợp có chủ đích của giai đoạn trước; không tạo User/Role mới. Các giao dịch test mới được giữ để demo, nên tổng Lead/Order/Payment/Event có tăng và không dùng số lượng giao dịch làm kết luận mất dữ liệu.

## 8. Not Tested và giới hạn

| Nội dung | Trạng thái | Phạm vi cần phân biệt |
| --- | --- | --- |
| Cài App mới hoàn toàn trên site khác | Not Tested | Đã migrate site local hiện hữu; chưa chứng minh clean install hay tái cài |
| Restore/reinstall/drop-site | Không thực hiện | Ngoài phạm vi và không dùng để kiểm thử A4.8 |
| WP-Cron nhiều giờ/ngày, không có traffic, Windows Task Scheduler | Not Tested | Chỉ có functional test tự động ~36 giây |
| Apache/CRM/Redis dừng rồi khởi động, mạng chập chờn dài hạn | Not Tested | Không có bằng chứng recovery hoặc soak test |
| Load test lớn, timeout khóa Redis, crash đúng thời điểm commit | Not Tested | Chỉ có đồng thời 4 request và các rollback nghiệp vụ cụ thể |
| Mọi giới hạn kích thước body/field, JSON lỗi, mọi tổ hợp permission | Not Tested đầy đủ | Source có kiểm tra; 37 case không bao phủ mọi nhánh |
| Cookie-only auth, Basic auth, source config hỏng, mọi vai trò khác | Not Tested trực tiếp đầy đủ | Không suy từ whitelist/permission source thành test Passed |
| Phone normalization 0/+84, email/phone Contact xung đột đầy đủ | Not Tested đầy đủ | Source hiện khớp chuỗi chính xác; guest case đã test |
| Tax/fee, nhiều store thật, custom Woo statuses, mọi plugin thanh toán | Not Tested | Local một store VND, native trạng thái được mapping |
| Payment gateway charge/refund thật | Not Tested | Chỉ date_paid_gmt và chứng từ test, không giao dịch tiền thật |
| Loyalty/Voucher/Refund/Reporting end-to-end | Not Tested | Chỉ bàn giao interface dữ liệu; chưa code nghiệp vụ các module đó |
| Ruff và kiểm tra bảo mật độc lập toàn hệ thống | Not Tested | Có syntax/JSON/diff check, không thay thế audit đầy đủ |
| Ảnh chụp UI và browser automation đầy đủ | Not Tested trong bộ 37 | DEMO_GUIDE liệt kê ảnh cần chụp; chưa tuyên bố đã có ảnh |

Action Scheduler còn có một số action Failed lịch sử ngoài webhook A4.8; bài kiểm tra không sửa hoặc chạy lại chúng. Chỉ kết luận theo action ID, context và Event của đơn test được quan sát.

## 9. Chạy lại có kiểm soát

Ba suite chính (trong Bench) tạo giao dịch test mới; schema suite rollback. Không cần chạy lại để đọc báo cáo:

```sh
bench --site crm.localhost execute hasaki_integration.tests.test_integration_http.run_lead
bench --site crm.localhost execute hasaki_integration.tests.test_integration_http.run_woocommerce
bench --site crm.localhost execute hasaki_integration.tests.test_schema.run
```

Test tự nhiên trên Windows: `python scripts/test_wp_cron.py`. Script tạo thêm đơn test và chỉ truy cập trang chủ, chờ tối đa 180 giây mỗi pha. Test doubles PHP: `D:\baitap\php\php.exe scripts/test_wordpress_bridge.php`.

Không gọi tên hàm test không tồn tại, không chạy Frappe fixture runner thay cho các lệnh trên, không gán Passed nếu script timeout/Failed. Xem [HANDOVER.md](HANDOVER.md) về điều kiện môi trường và quyền.
