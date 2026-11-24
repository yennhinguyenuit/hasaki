### Hasaki Integration — A4.8, Technical Contract v1.1

App hiện có trên `crm.localhost`, Frappe 15.127.1 và CRM 1.92.0. Source Windows được mount tại `/workspace/hasaki_integration`, liên kết vào Bench `/home/frappe/frappe-bench`. Không cần tạo lại App/site/container.

Đã triển khai 5 DocType: HSK Order, HSK Order Item, HSK Order Status History, HSK Payment, HSK Integration Event. Hai DocType Item/History là bảng con. Endpoint nghiệp vụ:

- `POST /api/method/hasaki_integration.wordpress.receive_lead`
- `POST /api/method/hasaki_integration.woocommerce.receive_order`

Lead dùng API Token của user hiện hữu có quyền tạo CRM Lead; `phone` lưu ở `mobile_no`, nguồn là `Web Form`, `message` lưu trong Comment và consent phải là JSON `true`. WooCommerce xác thực HMAC trên raw body, đối chiếu SKU hiện có, lưu khách vãng lai khi chưa khớp Contact, chống sự kiện cũ và chống ghi thanh toán trùng. Không tạo Master Data, sửa core, xử lý Loyalty/Voucher/Refund hoặc thay đổi BeautyMatch.

### Tài liệu và kết quả kiểm thử

- [Báo cáo triển khai](docs/IMPLEMENTATION_REPORT.md), [Data Dictionary Markdown](docs/DATA_DICTIONARY.md), [API Contract Markdown](docs/API_CONTRACT.md)
- [Chi tiết 37 test case và WP-Cron](docs/TEST_REPORT.md), [Hướng dẫn demo và ảnh minh chứng](docs/DEMO_GUIDE.md), [Bàn giao cho nhóm](docs/HANDOVER.md)
- [Technical Contract gốc v1.1](hasaki_integration/TECHNICAL_CONTRACT.md)
- [Data Dictionary được sinh từ schema](docs/DATA_DICTIONARY.json)
- [API Contract OpenAPI 3.0.3](docs/API_CONTRACT.openapi.json)
- [Kết quả HTTP Lead](docs/test_results_lead.json), [HTTP WooCommerce](docs/test_results_woocommerce.json), [schema/controller](docs/test_results_schema.json)
- [Tình trạng triển khai và giới hạn kiểm thử](docs/IMPLEMENTATION_STATUS.json)

Các bản ghi giao dịch test API dùng tên `A4.8 TEST`, submission/delivery ID `a48-test-` và store `a48-test`. Chúng được giữ lại để kiểm tra. Test schema chạy trong transaction rồi rollback. Các test không tạo user/role/Contact/Product/danh mục mới. Nếu đã có token tích hợp, test tái sử dụng và không đổi token; nếu chưa có, test cấp token tạm rồi khôi phục. Cấu hình store test tạm được khôi phục sau mỗi bộ test.

Báo cáo so sánh từng trường của dữ liệu nền và hash từng bảng trước/sau test. Frappe có thể tự cập nhật `User.last_active` khi có HTTP; thay đổi runtime này được ghi riêng, không được bỏ qua các thay đổi nghiệp vụ hoặc credentials.

### Migration và chạy lại kiểm thử

Thực hiện trong container, thư mục `/home/frappe/frappe-bench`. Backup đã được tạo trước lần migrate đầu tiên; đường dẫn nằm trong implementation status. Với lần thay đổi schema tiếp theo:

```sh
bench --site crm.localhost backup
bench --site crm.localhost migrate
bench --site crm.localhost execute hasaki_integration.tests.test_integration_http.run_lead
bench --site crm.localhost execute hasaki_integration.tests.test_integration_http.run_woocommerce
bench --site crm.localhost execute hasaki_integration.tests.test_schema.run
```

Đây là kiểm thử trên site local đã chuẩn bị theo yêu cầu. Không chạy Frappe test runner với fixture master và không restore/reinstall. Cài lại trên site khác chưa được kiểm thử. Các bộ test yêu cầu user hiện hữu `tuvan@hasaki.example`, user đọc Event `manager@hasaki.example`, và HTTP server port 8000.

### WordPress và WooCommerce

Plugin [Hasaki CRM Bridge](wordpress-plugin/hasaki-crm-bridge/hasaki-crm-bridge.php) đã cài và activate trên website hiện hữu `D:\baitap\htdocs\shopdongho`, URL **http://localhost:8080/shopdongho/**. XAMPP thực tế ở `D:\baitap`, Apache port 8080, WordPress 7.1.5, WooCommerce 10.9.4, PHP 8.2.12. Giữ theme `flatsome-hasaki-child`, database `shopdongho` và 200 sản phẩm. Plugin gắn form vào hộp hỗ trợ `hsk-support` có sẵn mà không sửa file theme hoặc tạo trang mới.

Hai webhook native `order.created` (ID 1) và `order.updated` (ID 2) đang Active. Nguồn được cấu hình là `http://localhost:8080/shopdongho`, store code `hasaki-local`, user CRM hiện hữu `tuvan@hasaki.example`. Không tạo user/role mới. Token được cấu hình có chủ đích trên tài khoản hiện hữu để WordPress gửi Lead.

Đối chiếu [toàn bộ catalog](docs/wordpress_catalog_compatibility.json) xác nhận đủ 200 SKU WordPress khớp `CRM Product.product_code`, không có SKU trùng hoặc thiếu; không sửa sản phẩm để ép khớp.

Trên Windows, `crm.localhost` chưa phân giải DNS tại thời điểm kiểm tra. Backend WordPress kết nối bằng `http://127.0.0.1:8000` và header `X-Frappe-Site-Name: crm.localhost`; ping và cả hai luồng tích hợp đã đạt. Không thay hosts hoặc cấu hình mạng máy.

WordPress `wp-config.php` chỉ được bổ sung một include có kiểm tra file tồn tại. Credentials ở `C:\Users\Yen Nhi\frappe-crm-backups\hasaki-integration-private\wordpress-secrets.php`, ngoài webroot và repository. Secret WooCommerce phía CRM nằm trong site config riêng của site. Database và wp-config WordPress đã backup trước thay đổi ở `C:\Users\Yen Nhi\frappe-crm-backups\wordpress-a48-20261124`; không restore/import.

Minh chứng thật: [form WordPress → Lead](docs/test_results_wordpress_e2e.json), [WooCommerce → Order/Payment](docs/test_results_woocommerce_e2e.json), [bảo toàn sản phẩm/theme](docs/wordpress_preservation.json). Lead E2E: `CRM-LEAD-2026-00130`. WooCommerce order test `1943` → `HSK-ORD-2026-00041`, Payment `HSK-PAY-2026-00042`. Thanh toán là dữ liệu test xác nhận qua `date_paid_gmt`, không gọi cổng thanh toán hoặc thu tiền thật. Hook email/trừ stock/tăng sales chỉ được tắt trong tiến trình CLI tạo đơn test; cấu hình vận hành của cửa hàng không thay đổi.

Native Action Scheduler actions của đúng đơn test được thực thi và trả HTTP 200. Khi update tới trước create, receiver trả 409; gửi lại sau create đã thành công. WooCommerce không bảo đảm thứ tự giao sự kiện. Không tự upsert đơn thiếu từ `order.updated`. Nếu gặp 409 thật cần kiểm tra và phát lại từ nguồn theo contract. Chưa chạy soak test WP-Cron không giám sát trong thời gian dài.

Bổ sung kiểm tra WP-Cron tự nhiên ngày 24/11: chỉ truy cập trang chủ, không chạy action thủ công hoặc gọi trực tiếp wp-cron.php. Đơn 1944 → `HSK-ORD-2026-00056`, Payment test `HSK-PAY-2026-00057`, log “started/complete via WP Cron”; hai pha đã đạt trong 35,88 giây. Xem [minh chứng WP-Cron](docs/test_results_wp_cron.json). Đây là functional test ngắn hạn, chưa phải soak test nhiều giờ/ngày hoặc kiểm tra không traffic.

WooCommerce thực tế có thể dùng lại Delivery-ID trong cùng giây. Event key vì vậy bao gồm topic, order ID, Delivery-ID và hash raw payload; không xem riêng Delivery-ID là định danh duy nhất. Khóa Order vẫn là `woo:{source_store}:{external_order_id}`.

Cấu hình ở backend WordPress bằng environment hoặc constant trong `wp-config.php`: `HASAKI_CRM_BASE_URL`, `HASAKI_CRM_API_KEY`, `HASAKI_CRM_API_SECRET`, `HASAKI_CRM_SITE` (mặc định `crm.localhost`), `HASAKI_WC_WEBHOOK_SECRET`. Không đưa secret vào JavaScript hay source Git. Base URL phải truy cập được từ backend WordPress, ví dụ địa chỉ host có port 8000 nếu WordPress chạy ngoài CRM container.

Form cũng có thể dùng shortcode `[hasaki_lead_form]`, hoặc form plugin hiện có gọi hàm PHP `hasaki_crm_send_lead($payload)`. Form có nonce, giới hạn số lần gửi, trường chống bot và giữ submission ID khi retry. Adapter xử lý thuộc tính `message` của Frappe và không chuyển tiếp token qua redirect.

WooCommerce dùng webhook gốc `order.created`/`order.updated`. Cấu hình `hasaki_woocommerce_stores` trong `crm.localhost/site_config.json` theo phần `x-config` của API Contract; URL nguồn là `home_url('/')` bỏ dấu `/` cuối, `user` phải là tài khoản CRM hiện hữu. Secret phải giống `HASAKI_WC_WEBHOOK_SECRET`. Nếu có WP-CLI, lệnh `wp --user=<admin-hiện-hữu> hasaki-crm sync-webhooks` thiết lập hai webhook và tái sử dụng cấu hình đã có cùng URL/topic. Không tạo user/sản phẩm. Script `scripts/activate_wordpress_bridge.php` thực hiện cùng việc đó bằng PHP XAMPP và đã được dùng trên site này.

Phần adapter được kiểm tra riêng bằng `php scripts/test_wordpress_bridge.php`; đây là test dùng WordPress API doubles, không phải minh chứng website WordPress thật.

Tham chiếu API nền: [WooCommerce Webhook](https://github.com/woocommerce/woocommerce/blob/trunk/plugins/woocommerce/includes/class-wc-webhook.php), [Webhook Data Store](https://github.com/woocommerce/woocommerce/blob/trunk/plugins/woocommerce/includes/data-stores/class-wc-webhook-data-store.php), [WordPress HTTP API](https://github.com/WordPress/wordpress-develop/blob/trunk/src/wp-includes/http.php).

### Cập nhật tài liệu schema/API

`scripts/build_schemas.py` tạo 5 JSON schema và Data Dictionary; `scripts/build_api_contract.py` tạo API Contract. Chỉ chạy sau khi đối chiếu và cập nhật contract. Controller và endpoint nằm hoàn toàn trong App này. Không tự push hoặc merge GitHub.

### License

MIT
