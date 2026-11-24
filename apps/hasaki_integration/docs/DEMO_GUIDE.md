# DEMO GUIDE — A4.8

## 1. Chuẩn bị phiên demo

1. Mở XAMPP hiện hữu ở D:\baitap; xác nhận Apache port 8080 và MySQL đang chạy. Không tạo WordPress mới.
2. Trong thư mục App trên Windows, chạy `docker ps`; cần crm-frappe-1, crm-mariadb-1, crm-redis-1 hoạt động. Không chạy restore/reinstall/drop-site để chuẩn bị demo.
3. Mở http://localhost:8080/shopdongho/ và đăng nhập WordPress bằng tài khoản admin hiện hữu ở /wp-admin/. Mở site CRM hiện hữu và đăng nhập tài khoản có quyền xem Lead/Order/Payment/Event. Trên Windows có thể dùng http://127.0.0.1:8000 khi site mặc định đã được cấu hình; backend luôn dùng site header crm.localhost.
4. Chuẩn bị tên test riêng, ví dụ A4.8 DEMO + giờ demo. Không dùng dữ liệu cá nhân thật. Không mở file cấu hình secrets khi quay/chụp màn hình.
5. Kiểm tra plugin Hasaki CRM Bridge Active. WooCommerce → Settings → Advanced → Webhooks: ID 1 order.created và ID 2 order.updated Active, đúng Delivery URL. Không hiển thị nội dung Secret.

Các mã mẫu có sẵn: Lead **CRM-LEAD-2026-00130**; Order WordPress **1943** → **HSK-ORD-2026-00041**, Payment **HSK-PAY-2026-00042**. Bài cron mới: WordPress **1944** → **HSK-ORD-2026-00056**, Payment **HSK-PAY-2026-00057**. Có thể demo chỉ đọc các bản ghi này để không tạo thêm giao dịch.

## 2. Demo Lead Form từ giao diện

1. Tại trang chủ, kéo xuống footer và bấm **Gửi yêu cầu hỗ trợ**. Hộp hsk-support phải có form Tên/Họ/Điện thoại/Email/Nội dung tư vấn/consent.
2. Nhập Tên A4.8 DEMO, Họ Khách thử, phone 0900000000, email demo@example.invalid, message hai dòng tiếng Việt. Tick đồng ý cung cấp thông tin.
3. Bấm Gửi yêu cầu tư vấn. Quan sát redirect và thông báo đã tiếp nhận. Không cần và không được đưa API Token vào JavaScript trình duyệt.
4. Trong CRM Leads, tìm theo tên và thời điểm vừa gửi, mở Lead. Đối chiếu first_name/last_name/mobile_no/email, source Web Form, Comment có message và đúng tiếng Việt.
5. Trong Frappe Desk dùng thanh tìm kiếm DocType HSK Integration Event; mở Event source WordPress, event_type lead.submitted, reference_name trỏ Lead vừa tạo, status Processed. submission_id nằm ở event_id/external_object_id.
6. Chứng minh chống trùng bằng đúng cùng request/submission_id, không bằng cách refresh rồi điền một form UUID mới. Cách đã kiểm thử sẵn: `python scripts/test_existing_wordpress.py` tạo một Lead test và gửi lại cùng POST. Báo cáo phải cho một Lead/một Comment. Chạy script này tạo thêm giao dịch test.
7. Với consent bỏ chọn, browser có thể chặn submit ngay do required. Backend cũng từ chối false; xem test case TC02/TC04 và báo cáo form E2E. Không sửa browser/source để ép consent vào dữ liệu khách thật.

## 3. Demo WooCommerce với dữ liệu mẫu có sẵn

1. WordPress → WooCommerce → Orders → mở order 1943 hoặc 1944. Đây là giao dịch test có created_via a48-integration-test, không phải đơn cần giao thật.
2. Quan sát ID, trạng thái, SKU, số lượng, tổng tiền, thông tin guest. Không chỉnh giá, stock hoặc sản phẩm để demo.
3. Trong Desk mở HSK Order bằng tên tương ứng. Kiểm tra source_channel WooCommerce, source_store hasaki-local, external_order_id, integration_key và bảng items.
4. Đối chiếu SKU/product Link, qty, unit_price, line_total, cost_price, status_history Pending → Processing. Với guest không khớp, customer để trống và guest_* có thông tin.
5. Mở HSK Payment theo order. Đối chiếu Paid, amount, paid_at, transaction_id test và payment_integration_key. Chỉ một Payment được ghi dù đã phát lại webhook.
6. Mở HSK Integration Event lọc source WooCommerce và external_object_id đúng ID. Phân biệt event nhận mới với một Order/Payment đã có; nhiều Event không có nghĩa nhiều đơn.

## 4. Demo webhook tự động, không bấm Run

Chọn một trong hai cách sau. Cách A chỉ đọc bằng chứng, cách B tạo một đơn test mới với guard bảo toàn stock/sales/email.

### Cách A — mở bằng chứng đã có

Mở [test_results_wp_cron.json](test_results_wp_cron.json), WooCommerce → Status → Scheduled Actions và tìm action IDs **1985, 1986, 1988**. Mở Logs, chỉ ra “started via WP Cron” và “complete via WP Cron”. Đối chiếu Order 1944 cùng CRM Order/Payment. Không bấm Run hoặc gọi process_action để chứng minh bài này.

### Cách B — chạy mới luồng tự nhiên

Tại thư mục App trên Windows:

```powershell
python scripts/test_wp_cron.py
```

Script dùng PHP XAMPP tạo một Order test từ sản phẩm hiện hữu; WooCommerce tự enqueue ở shutdown. Script chỉ GET trang chủ, quan sát queue và CRM, sau đó cập nhật date_paid_gmt test rồi chờ giao tự động. Không gọi wp-cron.php trực tiếp. Mỗi pha chờ tối đa 180 giây; đọc status thật trong docs/test_results_wp_cron.json, không gán Passed nếu timeout.

Nếu muốn thao tác từng bước bằng terminal và trình duyệt, tạo đơn bằng mode **cron-create**:

```powershell
& 'D:\baitap\php\php.exe' scripts/test_existing_woocommerce.php 'D:\baitap\htdocs\shopdongho' cron-create
```

Ghi ID mới được in ra, truy cập trang chủ bình thường và chờ Scheduled Action tự Complete. Sau khi Order CRM đã có, dùng ID đó với mode **cron-update**:

```powershell
& 'D:\baitap\php\php.exe' scripts/test_existing_woocommerce.php 'D:\baitap\htdocs\shopdongho' cron-update <TEST_ORDER_ID>
```

Thay placeholder bằng đúng đơn do script test tạo, không dùng đơn nghiệp vụ cũ. Mode update/cron-update kiểm tra tag test trước khi thay đổi. **Không dùng mode create/update/resume-created/replay để tuyên bố chạy cron tự nhiên**: các mode cũ có thể xử lý action/delivery thủ công theo thiết kế. Kiểm tra trạng thái chỉ đọc bằng `inspect_wp_cron.php <WP_ROOT> <TEST_ORDER_ID>` hoặc giao diện Scheduled Actions.

Chỉ đổi status Processing trong nguồn không phải minh chứng đủ về thanh toán. WooCommerce có thể tự điền date_paid khi đổi trạng thái; phải xem giá trị nguồn thực tế. Script cron-update chủ động đặt paid_at **test** và không gọi cổng thanh toán. Muốn chứng minh Processing nhưng chưa Paid, dùng payload/test TC31 không có date_paid_gmt.

## 5. Các lỗi demo có thể giải thích

| Tình huống | Cách giải thích / kiểm tra |
| --- | --- |
| Lead lỗi gửi | Kiểm tra thông tin, consent, backend kết nối CRM; không in token ra màn hình |
| Chưa thấy Order ngay | WordPress phát webhook nền; xem Pending/Complete và log, tiếp tục traffic thông thường |
| Update tới trước create | 409 CONFLICT; cần create thành công rồi giao lại; không tạo thủ công một bản Order trùng |
| SKU_NOT_FOUND | SKU chưa khớp master; không tạo sản phẩm để che lỗi |
| Cùng timestamp nhưng payload khác | 409 để giữ phiên bản đang có; không chỉnh hash/Event để vượt kiểm tra |
| Action Complete nhưng CRM không đúng | Action Scheduler Complete chưa đủ chứng minh HTTP thành công; đọc webhook response và Integration Event |
| Paid chưa có | Kiểm tra date_paid_gmt và Payment; không ép payment_status bằng SQL |

## 6. Danh sách ảnh minh chứng cần chụp

Chưa tạo hoặc tuyên bố đã chụp các ảnh dưới đây. Có thể đặt trong docs/evidence/ sau khi chụp, chỉ dùng dữ liệu test và che credentials/header Authorization/Secret.

| Tên ảnh đề xuất | Nội dung phải thấy |
| --- | --- |
| 01_wordpress_home.png | URL localhost:8080/shopdongho, giao diện Hasaki cũ |
| 02_bridge_active.png | Hasaki CRM Bridge Active cùng các plugin hiện hữu |
| 03_lead_form.png | Form trong hộp hỗ trợ, đủ field và consent |
| 04_lead_success.png | Thông báo tiếp nhận sau gửi |
| 05_crm_lead.png | Lead.name, mobile_no, source Web Form, email test |
| 06_lead_comment.png | Comment tiếng Việt hai dòng và liên kết Lead |
| 07_lead_event.png | submission_id, Processed và reference_name; không có token |
| 08_woo_webhooks.png | Hai topic Active và Delivery URL, che Secret |
| 09_woo_test_order.png | ID Order test, status, SKU, total |
| 10_hsk_order_items.png | integration_key, guest/customer và items/cost_price |
| 11_order_status_history.png | Pending → Processing, changed_by/changed_at |
| 12_hsk_payment.png | Một Payment, Paid, amount, paid_at, payment key |
| 13_wp_cron_actions.png | Action IDs 1985/1986/1988 hoặc IDs mới, Complete |
| 14_wp_cron_logs.png | Context WP Cron; không phải context chạy manual |
| 15_test_summary.png | 13+18+6 Passed và kết quả cron tự nhiên |
| 16_preservation.png | 200 sản phẩm và các hash preservation=true |

Không chụp wp-config/site_config/private secrets file. Không hiển thị nội dung nguyên bản Authorization, webhook Secret, database password hoặc encryption key.
