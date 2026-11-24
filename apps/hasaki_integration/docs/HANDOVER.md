# HANDOVER — A4.8

## 1. Phạm vi bàn giao và quyền sở hữu

App `hasaki_integration` chứa Lead API, WooCommerce receiver, 5 DocType giao dịch và bridge WordPress. Theo phụ lục v1.1, Nhi tạm triển khai local 5 schema; nhóm cần xác nhận schema không trùng trước khi chốt sở hữu/merge. Thành viên khác dùng Link/API/Document Events đã thống nhất, không tạo lại Order/Payment trong App của mình.

Không bàn giao một Event Bus, module Loyalty/Refund/Voucher/Reporting mới hay master thay thế Contact/Product. Các tên logic order_created/order_paid/order_cancelled/refund_completed/voucher_redeemed trong contract là quy ước tích hợp; source hiện **không phát một custom hook/event bus riêng mang các tên đó**. Dùng Document Events hoặc service của App phụ trách sau review.

## 2. Điều kiện trước khi dùng trên máy khác

1. Có Frappe/CRM/site của nhóm đang hoạt động; mốc đã test Frappe 15.127.1, CRM 1.92.0, Python Bench hiện hữu và MariaDB/Redis. Không nâng phiên bản thư viện để thay thế bước đối chiếu.
2. Có Contact, CRM Product (product_code, custom_cost_price, disabled), CRM Lead Source Web Form, CRM Lead Status phù hợp và các Role System Manager/Sales Manager/Sales User/CSKH Hasaki hiện hữu. App không có nhiệm vụ tạo dữ liệu thiếu.
3. Kiểm tra cả database và source các App đã cài xem 5 DocType HSK đã được định nghĩa ở đâu. Nếu tồn tại ở App khác, so sánh/tái sử dụng theo nhóm; không cài để ghi đè hoặc đổi module tùy ý.
4. Nhận **đầy đủ source đã review**. Hiện các thay đổi chưa được tự push/merge và nhiều file còn untracked; clone repository cũ không bảo đảm có phần việc này. Không copy backup SQL hoặc secret vào gói source.
5. Chọn user tích hợp đã có và quyền đã duyệt; local Nhi đang dùng tuvan@hasaki.example. Máy khác không nhất thiết có đúng tên này; không chạy helper local setup hardcode để tạo user thiếu.

## 3. Cài App và migrate

### Site đã cài App, gồm môi trường hiện tại

Trong Bench, xác nhận trước:

```sh
bench --site <SITE> list-apps
bench --site <SITE> backup
bench --site <SITE> migrate
```

Đổi <SITE> thành site thực tế. Không install-app lần nữa nếu App đã cài. Với local Docker, chạy lệnh qua `docker exec -w /home/frappe/frappe-bench crm-frappe-1 ...`. Đảm bảo source Windows mount `/workspace/hasaki_integration` và liên kết apps/hasaki_integration vẫn đúng.

### App chưa có trên Bench/site của thành viên

Chỉ thực hiện sau khi nguồn bàn giao đã hoàn chỉnh và không trùng schema. Ví dụ với bản repository/source đã được nhóm review:

```sh
bench get-app <DUONG_DAN_HOAC_URL_SOURCE_DA_REVIEW>
bench --site <SITE> backup
bench --site <SITE> install-app hasaki_integration
bench --site <SITE> migrate
```

Đây là hướng dẫn cho App còn thiếu, không phải yêu cầu tạo site/restore database mới. `bench get-app` từ Git có thể chỉ lấy file đã commit; các file untracked trên máy Nhi cần được bàn giao đầy đủ qua quy trình nhóm trước. Không tự push để “sửa” tình trạng này. Cài mới trên site khác **chưa được kiểm thử thực tế** trong kết quả A4.8 hiện tại.

Sau migrate, kiểm tra 5 DocType, module, child flag, field, permission và unique index theo DATA_DICTIONARY. Chạy kiểm tra chỉ đọc `hasaki_integration.a48_preflight.inspect_site` khi App đã import được. Không gọi script build_schemas trên schema của người khác chưa review; migrate đọc JSON đã có sẵn trong source.

## 4. Cấu hình WordPress/WooCommerce

Tái sử dụng WordPress đang có; local đã xác nhận D:\baitap\htdocs\shopdongho, URL http://localhost:8080/shopdongho/. Cài đúng thư mục wordpress-plugin/hasaki-crm-bridge vào wp-content/plugins và activate. Không thay theme hoặc nhập lại sản phẩm.

WordPress cần các constant/environment: HASAKI_CRM_BASE_URL, HASAKI_CRM_SITE, HASAKI_CRM_API_KEY, HASAKI_CRM_API_SECRET, HASAKI_WC_WEBHOOK_SECRET. Giá trị riêng bàn giao ngoài tài liệu/source. Local dùng file riêng ngoài webroot được wp-config include; không copy file đó vào Git hoặc thư mục public.

CRM site config cần dạng sau, toàn bộ giá trị trong dấu <> là placeholder:

```json
{
  "hasaki_woocommerce_stores": {
    "<WORDPRESS_HOME_URL_BO_DAU_GACH_CUOI>": {
      "source_store": "<MA_STORE_ON_DINH>",
      "secret": "<SECRET_BAN_GIAO_RIENG>",
      "user": "<USER_CRM_HIEN_HUU>"
    }
  }
}
```

Secret phải giống WooCommerce; header source là home_url('/') bỏ dấu / cuối. Base URL phải truy cập được **từ PHP WordPress**: local Windows dùng 127.0.0.1:8000 + X-Frappe-Site-Name crm.localhost; nếu PHP chạy trong container/máy khác, loopback đó không chỉ về máy Nhi. Kiểm tra ping từ backend trước.

Hai webhook native cần order.created/order.updated, Delivery URL receive_order. `hasaki_crm_sync_webhooks()` tái sử dụng cùng URL/topic, báo conflict nếu nhiều cấu hình trùng. Có WP-CLI thì dùng `wp --user=<ADMIN_HIEN_HUU> hasaki-crm sync-webhooks`; helper activate_wordpress_bridge.php thực hiện tương đương cho local đã cấu hình. Không chạy lại installer hardcode đường dẫn/tài khoản trên máy khác chưa đổi tham số/source phù hợp.

WP-Cron cần có traffic hoặc bộ lịch hệ thống được chủ môi trường thiết lập. Local đã chứng minh giao tự động qua WP Cron, chưa có soak test không traffic. Không cần thêm Frappe scheduled task để gửi webhook WooCommerce. Xem TEST_REPORT và DEMO_GUIDE.

## 5. Dùng Order và Payment trong App khác

Order có thể lấy bằng `frappe.get_doc("HSK Order", order_name)` và các Child Table `items`, `status_history`. Tạo bằng Document API để controller kiểm tra; không SQL INSERT/UPDATE để bỏ qua history, unique key hoặc tổng hợp Payment.

Ví dụ cấu trúc Order Manual (thay Link bằng bản ghi hiện hữu):

```python
order = frappe.get_doc({
    "doctype": "HSK Order",
    "source_channel": "Manual",
    "order_date": frappe.utils.now_datetime(),
    "currency": "VND",
    "status": "Pending",
    "grand_total": 100000,
    "items": [{
        "product": "<CRM_PRODUCT_NAME>", "sku": "<PRODUCT_CODE_TUONG_UNG>",
        "qty": 1, "unit_price": 100000, "line_total": 100000, "cost_price": 60000
    }]
}).insert()
```

Đây là mã mẫu, chưa chạy để tạo dữ liệu nền. Manual/POS được để integration_key null nếu không có ID ngoài; khi có source key riêng cần quy ước namespace để không va WooCommerce. Không đổi identity của Order WooCommerce đã có.

Payment là Document độc lập, không phải child row trong Order. Một Order có nhiều Payment, `order` bắt buộc Link đúng `name`. Mẫu xác nhận do nghiệp vụ có thẩm quyền thực hiện:

```python
payment = frappe.get_doc({
    "doctype": "HSK Payment", "order": "<HSK_ORDER_NAME>",
    "amount": 100000, "payment_method": "cash", "status": "Paid",
    "paid_at": frappe.utils.now_datetime(),
    "payment_integration_key": "<KHOA_NGHIEP_VU_DUY_NHAT>"
}).insert()
```

Không tự coi ví dụ này là thanh toán đã xảy ra. Paid phải có căn cứ nghiệp vụ thực; controller yêu cầu paid_at. Không đổi Payment.order/payment_integration_key sau lưu. Receiver WooCommerce bảo vệ amount/method/transaction ID của Payment đã xác nhận; controller dùng trực tiếp có tập kiểm tra riêng như DATA_DICTIONARY, không giả định tất cả kiểm tra receiver đều áp cho mọi caller.

Không tự set Order.payment_status. on_update/after_delete của Payment gọi tổng hợp và khóa parent; chỉ ghi thêm Paid khi thực sự được xác nhận. Với tổng Paid chưa đủ grand_total, trạng thái Order còn Pending; chưa có PartiallyPaid.

## 6. Tích hợp Loyalty

App của Trâm xử lý nghiệp vụ Loyalty; A4.8 không cộng điểm trong webhook. Điểm vào được đề xuất là Document Event **HSK Payment.on_update**, lọc lần chuyển sang Paid hoặc lần tạo Paid, rồi enqueue công việc sau commit. Order.customer có thể trống; không tự tạo Contact để cộng điểm.

Ví dụ cấu hình **đề xuất trong App của người sở hữu**, không phải hook đã được A4.8 cài:

```python
doc_events = {
    "HSK Payment": {"on_update": "<app_loyalty>.integration.after_payment_saved"}
}
```

Handler phải kiểm tra trạng thái cũ/mới và dùng `enqueue_after_commit=True` hoặc callback after_commit; endpoint A4.8 đang sở hữu transaction và Event chưa chắc đã Processed khi Payment.on_update đang chạy. Không gọi commit riêng trong hook, không gọi HTTP vòng lại cùng site khi có Document API.

Consumer cần khóa unique theo **tác động nghiệp vụ**, ví dụ loyalty:order_paid:{payment.name}, và rule của người sở hữu về nhiều Payment/hoàn điểm. Không dùng mỗi Integration Event.name để cộng điểm vì các delivery khác nhau có thể cùng tham chiếu một Order/Payment. Cờ items.loyalty_eligible mặc định 0 chưa có logic tự bật trong A4.8. Các điều kiện điểm, voucher, khách đủ điều kiện vẫn do App Loyalty xác định.

## 7. Tích hợp Refund và Voucher

Nguồn Woo status refunded không đủ để ghi hoàn tiền. App của Nghi quản lý Refund và bằng chứng hoàn tất; A4.8 không tạo HSK Refund hoặc thực hiện giao dịch hoàn tiền. Chỉ sau xác nhận hoàn tiền thật, App chủ quy trình mới ghi trạng thái/transaction phù hợp và trigger consumer sau commit với key chống lặp theo refund ID.

Payment có PartiallyRefunded/Refunded để tổng hợp nhưng không có amount_refunded trong schema A4.8. Vì vậy không thể tính số tiền hoàn chính xác chỉ từ Payment.status; Reporting cần chứng từ Refund thực tế của App sở hữu. Receiver WooCommerce không reset Payment Refunded về Paid khi nhận lại cùng bằng chứng thanh toán.

Voucher đã được nguồn trừ vào line_total không được trừ thêm trong Reporting hoặc gán thêm một khoản chi phí trùng. Không gọi API cộng điểm/hoàn tiền từ receiver A4.8 nếu chưa có interface đã duyệt của App chủ quản.

## 8. Tích hợp Reporting

| Dữ liệu | Trường / quy tắc sử dụng |
| --- | --- |
| Đơn và kênh | HSK Order, source_channel/source_store/order_date/status |
| Dòng bán sau giảm giá | HSK Order Item.line_total; không trừ lại Order.discount_total |
| Giá vốn lịch sử | qty × cost_price snapshot; không lấy giá vốn master hiện tại để ghi đè lịch sử |
| Thanh toán thực hiện | HSK Payment status Paid, amount/paid_at; Order.payment_status để lọc tổng hợp |
| Khách | Order.customer → Contact.name; guest để không xác định, không tự quy CLV cho một khách |
| Attribution | Lead/Deal/Contact liên kết đã có; Woo receiver không tự gán lead/deal từ email |
| Refund | Chứng từ hoàn tất thực của module Refund, không suy từ Woo status |
| Đồng bộ | Integration Event để điều tra, không dùng số Event làm số đơn hoặc doanh thu |

Không tính Order Cancelled hoặc chưa xác nhận đủ thanh toán vào doanh thu đã thực hiện theo contract. Tránh join trực tiếp nhiều Payment vào nhiều Item rồi SUM gây nhân bản; aggregate Payment theo Order trước hoặc dùng EXISTS. Reporting có thể cần rule phân bổ tiền nhận từng phần; trạng thái Pending không đồng nghĩa chưa từng có một Payment Paid nhỏ hơn tổng.

Source chưa tạo báo cáo CLV/CAC/ABC, không tự phân bổ khách vãng lai, không tính refund/voucher hai lần. Mọi giả định tài chính và module cá nhân do Tường phụ trách phải được ghi rõ trong App Reporting.

## 9. Vận hành, điều tra và bàn giao kiểm thử

- Event Received/Processed/Failed, reference và error_summary là điểm bắt đầu điều tra. Failed có thể tồn tại dù chứng từ đã rollback; không xóa Event hoặc sửa hash để ép retry.
- 401: kiểm tra secret/token bằng kênh riêng, source URL và quyền; không dán credentials vào issue/log/ảnh.
- 409: phân biệt update trước create, cùng timestamp khác hash, Payment conflict và khóa bận. Điều tra nguồn rồi phát lại theo nguyên tắc idempotency; App không có queue tự repair mọi conflict.
- 422: kiểm tra product_code có sẵn. Không tạo master giả để “Passed”.
- Action Complete chỉ cho biết callback của scheduler kết thúc; xác nhận thêm response HTTP, Event Processed và dữ liệu CRM.
- Giữ source/API/Data Dictionary đồng bộ, test trên môi trường phù hợp, review schema chung trước merge. Không restore SQL để merge source.

Source test và minh chứng nằm trong TEST_REPORT. Các suite hardcode local user/URL; thành viên khác phải rà soát các điều kiện này trước chạy. File backup và secrets không nằm trong gói source. Việc push/merge và thay đổi App của thành viên khác tuân theo quy trình review của nhóm.
