# TECHNICAL CONTRACT v1.1 – HASAKI CRM

## Phụ lục cập nhật bắt buộc (24/11/2026)

Các quyết định trong phụ lục này **ưu tiên hơn mọi nội dung mâu thuẫn trong bản v1.0 bên dưới**. Các quy tắc không được thay đổi vẫn giữ nguyên.

- Mỗi thành viên sử dụng Custom App riêng, cùng cài trên Frappe Site `crm.localhost` khi tích hợp. Không tạo App `hasaki_crm` chung.
- App A4.8 của Nhi: `hasaki_integration`, đã tạo và cài trên site, source Windows `C:\Users\Yen Nhi\frappe-crm\hasaki_integration`, mount `/workspace/hasaki_integration`, liên kết `/home/frappe/frappe-bench/apps/hasaki_integration`. Không tạo hoặc cài lại App nếu đã cài.
- Nhi tạm sở hữu và triển khai trên local năm DocType: `HSK Order`, `HSK Order Item`, `HSK Order Status History`, `HSK Payment`, `HSK Integration Event`. Chỉ xác lập quyền sở hữu dùng chung sau khi nhóm xác nhận không trùng schema; không push/merge trước khi Nhi duyệt. Nếu DocType đã tồn tại ở site hoặc source khác, kiểm tra và tái sử dụng, không tạo đè.
- Endpoint A4.8: `POST /api/method/hasaki_integration.wordpress.receive_lead`, `POST /api/method/hasaki_integration.woocommerce.receive_order`. Các endpoint của thành viên khác thuộc App riêng của họ.
- Ánh xạ Lead Form: `phone` → `CRM Lead.mobile_no`; `message` → Comment liên kết Lead; nguồn `Web Form` đã có. Không tạo Contact mới. `submission_id` lưu trong Integration Event; consent phải là true.
- Bổ sung kỹ thuật cho HSK Order: `items` (Table → HSK Order Item), `status_history` (Table → HSK Order Status History), `last_source_modified_at` (Datetime), `last_source_payload_sha256` (Data). HSK Payment: `payment_integration_key` (Data, Unique). HSK Order Status History: `status` (Select theo Order), `changed_at` (Datetime), `changed_by` (Link → User), `note` (Small Text). HSK Integration Event `reference_name` là Dynamic Link có options `reference_doctype`.
- Khóa duy nhất của POS/Manual có thể bỏ trống khi không có mã ngoài hệ thống; WooCommerce phải có khóa `woo:{source_store}:{external_order_id}`. Không sửa dữ liệu nền hoặc tạo Master Data mới, không thêm ba custom field Contact đã loại bỏ ở v1.0. Bỏ qua BeautyMatch, không chỉnh sửa hay xóa.
- Giai đoạn hiện tại: kiểm tra App và schema thực tế, dùng source trong App hiện hữu, triển khai và kiểm thử Lead API trước; sau đó mới kết nối WordPress và WooCommerce. Backup trước khi migrate; không restore/reinstall/drop-site, không tạo lại container, không sửa core. Kiểm thử các thay đổi trên môi trường phù hợp và ghi nhận Passed/Failed/Not Tested bằng kết quả thực tế.
- Không tự push, merge hoặc đưa secrets/backup lên GitHub; branch nhóm của Nhi là `nhi` (khác branch nội bộ của App). Các chức năng cá nhân và phần việc của Trâm, Nghi, Tường giữ nguyên.

---

## Nội dung gốc v1.0 (tham chiếu; phụ lục trên có quyền ưu tiên)

## I. KIẾN TRÚC VÀ MASTER DATA

### 1. Nguyên tắc hệ thống

1. Tiếp tục sử dụng Frappe CRM và database MariaDB đã được Trâm bàn giao.
2. Không cài đặt lại hệ thống, tạo site mới để thay thế site chung hoặc nhập lại dữ liệu nền.
3. Không tạo thêm Master Data DocType, không bổ sung danh mục hoặc bản ghi master giả lập mới trong TASK 2.
4. Không chỉnh sửa trực tiếp mã nguồn gốc của Frappe Framework và Frappe CRM.
5. Mọi DocType giao dịch mới được liên kết với dữ liệu nền hiện có thông qua Link Field.
6. Các thành viên phát triển trên branch riêng và chỉ merge sau khi kiểm thử.
7. Không tạo lại Custom App đã có. Phần mã nguồn trên local cần được đồng bộ lên GitHub dưới dạng có thể cài đặt và migrate được.

### 2. Master Data giữ nguyên

| **DocType**          | **Quy định**                         |
| -------------------- | ------------------------------------ |
| Contact              | Sử dụng dữ liệu khách hàng đã có     |
| Address              | Sử dụng địa chỉ đã có                |
| User                 | Sử dụng tài khoản đã cấu hình        |
| Role                 | Sử dụng Role và Role Profile hiện có |
| CRM Lead Source      | Sử dụng 8 nguồn đã cấu hình          |
| CRM Product          | Sử dụng 200 sản phẩm đã nhập         |
| HSK Product Category | Sử dụng 14 danh mục đã nhập          |

**Không tạo mới:** Customer, Product, Product Category, Brand, Branch, Department, Sales Channel, Payment Method, Social Channel hoặc các Master DocType khác chỉ để thay thế dữ liệu hiện có.

Trường hợp cần phân biệt cửa hàng, kênh bán hoặc phương thức thanh toán, ưu tiên sử dụng giá trị Select/Data hoặc thông tin đã được lưu trên chứng từ giao dịch, không tạo bảng danh mục riêng.

Các danh mục nghiệp vụ thuộc Custom App cá nhân đã được phê duyệt vẫn thực hiện theo phạm vi cá nhân; không phát sinh nhiệm vụ tạo master mới trong TASK nhóm.

### 3. Các DocType CRM có sẵn

| **DocType**          | **Trường liên kết cần dùng**                                                 |
| -------------------- | ---------------------------------------------------------------------------- |
| Contact              | `name`, `custom_customer_id`, `email_id`, `mobile_no`                        |
| CRM Lead             | `name`, `source`, `status`, `lead_owner`                                     |
| CRM Deal             | `name`, `lead`, `contact`, `status`, `deal_value`                            |
| CRM Product          | `name`, `product_code`, `product_name`, `standard_rate`, `custom_cost_price` |
| HSK Product Category | name                                                                         |
| CRM Call Log         | `name`, `reference_doctype`, `reference_docname`                             |
| CRM Task             | `name`, `assigned_to`, `reference_doctype`, `reference_docname`              |
| User                 | name                                                                         |

**Quy định khóa liên kết:**

- Khách hàng: `Contact.name`.
- Sản phẩm: `CRM Product.name`.
- SKU: `CRM Product.product_code`.
- Lead: `CRM Lead.name`.
- Deal: `CRM Deal.name`.
- Nhân viên: `User.name`.
- Nguồn Lead: `CRM Lead Source.name`.

Các mã `KH0001`, `HSK-xxxxxx` và mã đơn hiển thị là mã nghiệp vụ, không thay thế khóa Link.

**Không thêm ba field `custom_lead_source`, `custom_lead_id`, `custom_first_order_date` vào Contact trong TASK 2.** Tường tính nguồn khách hàng và ngày mua đầu tiên từ dữ liệu Lead/Deal/Order. Nếu không truy vết được nguồn, báo cáo ghi nhận là “Không xác định”, không tự suy đoán.



---



## II. CHỐT DOCTYPE NGHIỆP VỤ VÀ NGƯỜI SỞ HỮU

| **DocType**                              | **Người sở hữu cấu trúc**      | **Người sử dụng**    |
| ---------------------------------------- | ------------------------------ | -------------------- |
| HSK Order                                | Nghi – theo nghiệp vụ cá nhân  | Nhi, Trâm, Tường     |
| HSK Order Item                           | Nghi                           | Nhi, Trâm, Tường     |
| HSK Order Status History                 | Nghi                           | Nhi, Tường           |
| HSK Payment                              | Nghi                           | Nhi, Trâm, Tường     |
| HSK Complaint                            | Nghi                           | Tường đọc báo cáo    |
| HSK Return Request / Inspection / Refund | Nghi                           | Tường đọc báo cáo    |
| HSK Loyalty Account / Transaction        | Trâm – theo nghiệp vụ cá nhân  | Tường                |
| HSK Reward / Reward Redemption           | Trâm                           | Tường                |
| HSK Voucher / Voucher Usage              | Tường – theo nghiệp vụ cá nhân | Trâm, Tường          |
| HSK Consultation Request                 | Nhi – theo nghiệp vụ cá nhân   | Trâm nếu có liên kết |
| HSK Integration Event                    | Nhi – A4.8                     | Nghi đọc để kiểm thử |
| HSK Social Conversation                  | Trâm – A4.9.1                  | Nhi, Tường           |
| HSK Message Log                          | Trâm – A4.9.1                  | Nhi, Tường           |
| HSK Activity Log                         | Tường – A4.5                   | Tường                |
| HSK Activity Cost Pool                   | Tường – A4.5                   | Tường                |
| HSK Marketing Cost                       | Tường – A4.5                   | Tường                |
| HSK Employee Cost Rate                   | Tường – A4.5                   | Tường                |

**Quy tắc sở hữu:**

- Chỉ người sở hữu được chủ động thay đổi schema, controller và workflow của DocType đó.
- Người khác sử dụng Link Field, API hoặc service đã công bố.
- Không tự sửa tên field của DocType do thành viên khác sở hữu.
- Không tạo lại cùng một DocType dưới tên khác.
- Nếu DocType đã tồn tại trên site, giữ nguyên tên thực tế và so sánh schema trước khi bổ sung.
- Nếu thay đổi giao diện dữ liệu dùng chung, người sở hữu cập nhật Data Dictionary trước khi merge.

Việc xác định người sở hữu ở đây không thay đổi phân công Custom App cá nhân.



---



## III. CHỐT CẤU TRÚC ĐƠN HÀNG VÀ THANH TOÁN

### 1. HSK Order

| **Fieldname**     | **Type**        | **Quy định**                               |
| ----------------- | --------------- | ------------------------------------------ |
| customer          | Link → Contact  | Có thể trống nếu chưa đối chiếu được khách |
| lead              | Link → CRM Lead | Không bắt buộc                             |
| deal              | Link → CRM Deal | Không bắt buộc                             |
| source_channel    | Select          | WooCommerce, POS, Manual                   |
| source_store      | Data            | Mã website/cửa hàng nguồn                  |
| external_order_id | Data            | ID đơn hàng ngoài CRM                      |
| integration_key   | Data, Unique    | Khóa chống tạo đơn trùng                   |
| order_date        | Datetime        | Ngày đặt hàng                              |
| status            | Select          | Trạng thái xử lý đơn                       |
| payment_status    | Select          | Tổng hợp từ Payment và Refund              |
| currency          | Data            | VND                                        |
| grand_total       | Currency        | Tổng tiền phải thanh toán                  |
| discount_total    | Currency        | Tổng giảm giá, dùng đối soát               |
| shipping_total    | Currency        | Phí giao hàng                              |
| guest_full_name   | Data            | Thông tin khách chưa liên kết Contact      |
| guest_phone       | Data            | Số điện thoại khách chưa liên kết          |
| guest_email       | Data            | Email khách chưa liên kết                  |

### 2. HSK Order Item

| **Fieldname**    | **Type**           |
| ---------------- | ------------------ |
| product          | Link → CRM Product |
| external_line_id | Data               |
| sku              | Data               |
| qty              | Float              |
| unit_price       | Currency           |
| discount_amount  | Currency           |
| line_total       | Currency           |
| cost_price       | Currency           |
| loyalty_eligible | Check              |

`line_total` là tổng tiền dòng hàng sau khi phân bổ giảm giá liên quan. `discount_total` của Order dùng để đối soát, không được trừ lần thứ hai khi đã dùng giá trị `line_total`.

`cost_price` là giá vốn tại thời điểm đặt hàng, được lưu theo dòng hàng để phục vụ báo cáo lịch sử.

### 3. HSK Payment

| **Fieldname**  | **Type**               |
| -------------- | ---------------------- |
| order          | Link → HSK Order       |
| amount         | Currency               |
| payment_method | Data                   |
| status         | Select                 |
| transaction_id | Data                   |
| paid_at        | Datetime               |
| payment_proof  | Attach, không bắt buộc |

**Trạng thái chuẩn:**

- Order: `Pending`, `Processing`, `Shipping`, `Completed`, `Cancelled`.
- Payment: `Pending`, `Paid`, `Failed`, `PartiallyRefunded`, `Refunded`.

Mọi thành viên sử dụng đúng các giá trị lưu trong database. Nhãn tiếng Việt chỉ dùng để hiển thị trên giao diện.

**Quy tắc nghiệp vụ:**

1. WooCommerce và POS dùng chung HSK Order.
2. Một Order có nhiều Order Item và có thể có nhiều Payment.
3. Đơn mới tạo không mặc định đã thanh toán.
4. Không ghi nhận thanh toán thành công chỉ vì đơn chuyển sang Processing.
5. Không tự tạo Contact khi không tìm thấy khách hàng. Order lưu thông tin khách vãng lai và chờ đối chiếu.
6. Không tạo Master Data mới khi xử lý dữ liệu không khớp.
7. Không tính đơn chưa thanh toán vào doanh thu đã thực hiện.
8. Refund chỉ tác động báo cáo khi hoàn tiền thực sự được ghi nhận hoàn tất.
9. Chuyển trạng thái quan trọng phải có lịch sử và không xử lý tác động nghiệp vụ trùng lặp.



---



## IV. CHỐT API CONTRACT

### 1. Nguyên tắc API

- Frappe sử dụng Resource API `/api/resource/...` cho CRUD và Method API `/api/method/...` cho nghiệp vụ tùy chỉnh.
- API và Webhook được phân quyền theo chức năng.
- Request/Response dùng JSON, ngoại trừ bước xác minh Webhook cần đọc raw request body.
- Mỗi API có owner duy nhất.
- Không lưu secret trong source code.
- Phản hồi thành công phải có trạng thái và mã bản ghi liên quan.
- Lỗi phải có mã lỗi rõ ràng.
- Không tạo dữ liệu trùng khi request được gửi lại.

### 2. Danh sách API thống nhất

| **API**                                                       | **Method**             | **Owner**     | **Chức năng**                                   |
| ------------------------------------------------------------- | ---------------------- | ------------- | ----------------------------------------------- |
| /api/method/hasaki_crm.integrations.wordpress.receive_lead    | POST                   | Nhi           | Tiếp nhận Lead Form                             |
| /api/method/hasaki_crm.integrations.woocommerce.receive_order | POST                   | Nhi           | Tiếp nhận WooCommerce Webhook                   |
| /api/method/hasaki_crm.social_inbox.api.receive_webhook       | GET/POST theo nền tảng | Trâm          | Xác minh/nhận sự kiện chat nếu tích hợp thực tế |
| /api/method/hasaki_crm.social_inbox.api.send_reply            | POST                   | Trâm          | Gửi phản hồi từ giao diện CRM                   |
| /api/resource/CRM%20Lead                                      | GET/POST/PUT/DELETE    | Nghi kiểm thử | Minh chứng Resource API A4.7                    |

Các đường dẫn Custom API ở trên là contract cho source code sẽ triển khai; cần đối chiếu đường dẫn module thực tế nếu App hiện hữu đã sử dụng namespace khác.

Nghi chỉ thực nghiệm API trên dữ liệu test, không viết lại API tích hợp WordPress hoặc Social Inbox do Nhi và Trâm phụ trách.

### 3. WordPress Lead Form → Frappe CRM

**Endpoint:** `POST /api/method/hasaki_crm.integrations.wordpress.receive_lead`

**Xác thực:** API Token của tài khoản tích hợp, được sử dụng từ WordPress backend, không đặt trong JavaScript trình duyệt.

| **Request field** | **Bắt buộc** | **Ánh xạ**                         |
| ----------------- | ------------ | ---------------------------------- |
| submission_id     | Có           | Khóa chống gửi form trùng          |
| first_name        | Có           | CRM Lead.first_name                |
| last_name         | Không        | CRM Lead.last_name                 |
| phone             | Có           | Số điện thoại Lead                 |
| email             | Không        | Email Lead                         |
| message           | Có           | Nội dung yêu cầu tư vấn            |
| consent           | Có           | Xác nhận đồng ý cung cấp thông tin |

**Quy tắc xử lý:**

1. Kiểm tra xác thực và dữ liệu đầu vào.
2. Kiểm tra `submission_id` đã xử lý hay chưa.
3. Tạo CRM Lead từ thông tin khách gửi.
4. Gán nguồn tiếp nhận `Web Form` theo cấu hình hiện có.
5. Không tự động tạo Contact.
6. Lưu mã sự kiện vào HSK Integration Event.
7. Trả kết quả chứa mã Lead và trạng thái xử lý.
8. Nếu gửi lại cùng `submission_id`, trả kết quả đã lưu, không tạo Lead thứ hai.

### 4. WooCommerce → Frappe CRM

**Endpoint:** `POST /api/method/hasaki_crm.integrations.woocommerce.receive_order`

**Sự kiện nhận:**

-

```
order.created
```

1.

```
order.updated
```

**Nguồn dữ liệu:** Payload Webhook gốc của WooCommerce.

| **Trường WooCommerce**                    | **Trường/đối tượng CRM**                         |
| ----------------------------------------- | ------------------------------------------------ |
| id                                        | HSK Order.external_order_id                      |
| status                                    | HSK Order.status sau khi ánh xạ                  |
| date_created_gmt                          | HSK Order.order_date                             |
| date_modified_gmt                         | Dùng kiểm tra phiên bản cập nhật                 |
| date_paid_gmt                             | HSK Payment.paid_at nếu thanh toán được xác nhận |
| `billing.first_name`, `billing.last_name` | Dữ liệu đối chiếu Contact                        |
| `billing.phone`, `billing.email`          | Dữ liệu đối chiếu Contact                        |
| line_items[].sku                          | CRM Product.product_code                         |
| line_items[].quantity                     | HSK Order Item.qty                               |
| line_items[].total                        | HSK Order Item.line_total                        |
| discount_total                            | HSK Order.discount_total                         |
| shipping_total                            | HSK Order.shipping_total                         |
| total                                     | HSK Order.grand_total                            |
| currency                                  | HSK Order.currency                               |

**Quy tắc:**

1. Xác thực `X-WC-Webhook-Signature` bằng HMAC-SHA256 trên raw request body, sử dụng Webhook Secret đã cấu hình.
2. Không ghi dữ liệu nếu chữ ký không hợp lệ.
3. Khóa đơn hàng là `woo:{source_store}:{external_order_id}`.
4. `order.created` tạo đơn nếu chưa tồn tại.
5. `order.updated` cập nhật đơn đã có; không tạo bản sao.
6. Kiểm tra thời điểm cập nhật để tránh sự kiện cũ ghi đè dữ liệu mới.
7. SKU phải đối chiếu được với CRM Product.
8. SKU không tồn tại được ghi lỗi để xử lý, không tạo CRM Product mới.
9. Khách chưa có trong Contact được ghi nhận ở thông tin khách vãng lai, không tạo Contact mới.
10. Hệ thống ghi lịch sử đồng bộ và kết quả xử lý.

### 5. HSK Integration Event

Đây là **DocType giao dịch kỹ thuật**, không phải Master Data.

| **Fieldname**      | **Ý nghĩa**                   |
| ------------------ | ----------------------------- |
| source             | WordPress/WooCommerce         |
| event_id           | Mã định danh sự kiện          |
| idempotency_key    | Khóa duy nhất chống xử lý lặp |
| external_object_id | ID bản ghi từ hệ thống ngoài  |
| event_type         | Loại sự kiện                  |
| payload_sha256     | Hash của payload              |
| status             | Received, Processed, Failed   |
| reference_doctype  | DocType đã tác động           |
| reference_name     | Tên bản ghi đã tác động       |
| processed_at       | Thời điểm xử lý               |
| error_summary      | Mô tả lỗi                     |

Không lưu toàn bộ thông tin cá nhân của khách hàng trong log nếu không cần thiết.

### 6. Quy ước Response và lỗi

**Response thành công:** Chứa `ok`, `code`, `data` với mã bản ghi và `idempotent` nếu là request gửi lặp.

Frappe Method API có thể trả phần kết quả trong thuộc tính `message`; client phía WordPress phải đọc đúng cấu trúc thực tế.

**Mã lỗi nghiệp vụ thống nhất:**

| **Code**          | **Ý nghĩa**                     |
| ----------------- | ------------------------------- |
| VALIDATION_ERROR  | Dữ liệu thiếu hoặc không hợp lệ |
| UNAUTHORIZED      | Chưa được xác thực              |
| INVALID_SIGNATURE | Chữ ký Webhook không hợp lệ     |
| SKU_NOT_FOUND     | Không ánh xạ được sản phẩm      |
| CONFLICT          | Dữ liệu phát sinh xung đột      |
| INTERNAL_ERROR    | Lỗi xử lý hệ thống              |

Các lỗi nghiệp vụ phải trả HTTP status phù hợp; request trùng hợp lệ có thể trả thành công cùng mã bản ghi cũ.



---



## V. CHỐT SOCIAL INBOX – A4.9.1

### 1. Phạm vi

Trâm triển khai Hasaki Social Inbox ngay trên Frappe CRM, ưu tiên Facebook Messenger. Zalo OA là kênh mở rộng nếu có đủ quyền truy cập API.

Chức năng phải có:

- Danh sách hội thoại.
- Giao diện đọc và trả lời tin nhắn.
- Lịch sử gửi/nhận.
- Phân công nhân viên CSKH.
- Trạng thái xử lý.
- Tìm kiếm, lọc hội thoại.
- Liên kết Contact, Lead hoặc Deal.

### 2. HSK Social Conversation

| **Fieldname**            | **Type**                                        |
| ------------------------ | ----------------------------------------------- |
| customer                 | Link → Contact, không bắt buộc                  |
| lead                     | Link → CRM Lead, không bắt buộc                 |
| deal                     | Link → CRM Deal, không bắt buộc                 |
| consultation_request     | Link → HSK Consultation Request, không bắt buộc |
| platform                 | Select: Facebook, Zalo, Demo                    |
| provider_account_id      | Data                                            |
| external_user_id         | Data                                            |
| external_conversation_id | Data                                            |
| assigned_to              | Link → User                                     |
| status                   | Select                                          |
| last_message_at          | Datetime                                        |

**Trạng thái:** `New`, `Open`, `Pending`, `Resolved`, `Closed`.

### 3. HSK Message Log

| **Fieldname**       | **Type**                                |
| ------------------- | --------------------------------------- |
| conversation        | Link → HSK Social Conversation          |
| external_message_id | Data                                    |
| direction           | Select: Inbound, Outbound               |
| sender              | Data                                    |
| message_content     | Long Text                               |
| sent_at             | Datetime                                |
| delivery_status     | Select: Pending, Received, Sent, Failed |

HSK Message Log là DocType độc lập, không phải Child Table, để thuận tiện phân trang, tra cứu và đồng bộ tin nhắn.

**Quy tắc tích hợp:**

1. Không tạo thêm HSK Social Channel Master DocType.
2. Một Contact có nhiều hội thoại.
3. Một hội thoại có nhiều tin nhắn.
4. Khách Facebook/Zalo được đối chiếu bằng ID theo nền tảng, không mặc định có số điện thoại.
5. Không tự động tạo Contact khi chưa xác định được khách.
6. Tin nhắn gửi/nhận cần có mã chống ghi trùng.
7. Nếu không kết nối API thực tế, dùng nền tảng `Demo` và ghi rõ giao diện chat mô phỏng.
8. Không để hai Custom App cùng sở hữu HSK Message Log.



---



## VI. CHỐT SỰ KIỆN NGHIỆP VỤ DÙNG CHUNG

Các chức năng chạy trên cùng một Frappe Site có thể sử dụng Document Events và service Python, không cần gọi HTTP vòng lại chính server.

| **Sự kiện logic**       | **Điều kiện phát sinh**     | **Dữ liệu tối thiểu**                      |
| ----------------------- | --------------------------- | ------------------------------------------ |
| order_created           | Tạo Order hợp lệ            | `order_name`, `customer`, `source_channel` |
| order_paid              | Thanh toán chuyển sang Paid | `order_name`, `payment_name`, `event_id`   |
| order_cancelled         | Đơn chuyển sang Cancelled   | `order_name`, `event_id`                   |
| refund_completed        | Refund chuyển sang hoàn tất | `order_name`, `refund_name`, `amount`      |
| voucher_redeemed        | Voucher được sử dụng hợp lệ | `order_name`, `voucher_name`, `amount`     |
| social_message_received | Nhận tin nhắn mới           | `conversation_name`, `message_name`        |

**Quy định:**

- Đây là tên sự kiện logic thống nhất, không mặc định phải tạo một Event Bus riêng.
- Bên phát sinh sự kiện không tự xử lý nghiệp vụ thuộc App khác.
- Không cộng điểm trực tiếp trong Webhook WooCommerce.
- Không ghi giảm giá voucher lần thứ hai trong Reporting.
- Không tự động hoàn tiền chỉ vì cập nhật trạng thái đơn.
- Mỗi tác động nghiệp vụ phải có khóa chống thực hiện lặp.
- Xử lý chỉ được ghi nhận sau khi giao dịch nguồn hợp lệ và được lưu thành công.

Đối với Loyalty, Refund và Voucher, các điều kiện nghiệp vụ cụ thể vẫn do người sở hữu quy trình cá nhân kiểm soát.



---



## VII. CHỐT DỮ LIỆU CHI PHÍ VÀ REPORTING – TƯỜNG

### 1. DocType cần sử dụng

| **DocType**            | **Trường dữ liệu chính**                                                                                                                                 |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HSK Activity Log       | `activity_type`, `customer`, `employee`, `reference_doctype`, `reference_name`, `activity_date`, `duration_hours`, `driver_quantity`, `source_event_key` |
| HSK Activity Cost Pool | `activity_type`, `period_start`, `period_end`, `total_cost`                                                                                              |
| HSK Marketing Cost     | `campaign`, `lead_source`, `period_start`, `period_end`, `amount`                                                                                        |
| HSK Employee Cost Rate | `employee`, `hourly_rate`, `effective_from`, `effective_to`                                                                                              |

**Không tạo mới HSK Activity Type Master DocType.** Trường `activity_type` dùng Select thống nhất theo tám giá trị:

| **Giá trị lưu**   | **Hoạt động**                        |
| ----------------- | ------------------------------------ |
| consultation      | Tiếp nhận, tư vấn                    |
| care_contact      | Gọi điện, nhắn tin CSKH              |
| order_processing  | Xử lý đơn hàng                       |
| delivery          | Đóng gói, giao hàng                  |
| complaint         | Xử lý khiếu nại                      |
| return_inspection | Kiểm tra đổi trả                     |
| refund            | Thanh toán/hoàn tiền                 |
| loyalty_voucher   | Vận hành tích điểm, đổi quà, voucher |

Các giá trị này dùng thống nhất trong Activity Log, Cost Pool và Dashboard.

### 2. Nguồn dữ liệu duy nhất

| **Chỉ số**         | **Nguồn**                                                              |
| ------------------ | ---------------------------------------------------------------------- |
| Lead và Conversion | CRM Lead, CRM Deal                                                     |
| Doanh thu          | HSK Order và HSK Order Item                                            |
| Thanh toán         | HSK Payment                                                            |
| Giá vốn            | HSK Order Item.cost_price                                              |
| Hoàn tiền          | HSK Refund                                                             |
| Chi phí quà        | HSK Reward Redemption và HSK Reward                                    |
| Sử dụng voucher    | HSK Voucher Usage                                                      |
| Chi phí Marketing  | HSK Marketing Cost                                                     |
| Chi phí vận hành   | HSK Activity Cost Pool                                                 |
| Chi phí nhân sự    | HSK Activity Log, HSK Employee Cost Rate                               |
| Chi phí CSKH       | Activity Log tham chiếu Call Log, Social Conversation hoặc Message Log |

**Không tạo lại các bảng khách hàng, đơn hàng, sản phẩm hoặc lịch sử tin nhắn chỉ để phục vụ Reporting.**

### 3. Quy ước tài chính

- Tiền tệ: VND.
- Kỳ phân tích chính: Quý.
- Dữ liệu lịch sử mẫu: 01/11/2024 – 31/10/2026.
- Doanh thu bán hàng lấy từ dòng hàng đã thanh toán, sau giảm giá, không cộng đơn hủy hoặc chưa thanh toán.
- Tổng giảm giá trên Order dùng để đối soát; không trừ lại nếu đã phản ánh trong `line_total`.
- Refund chỉ được trừ khi trạng thái hoàn tiền là hoàn tất.
- Voucher đã giảm vào doanh thu không được hạch toán thêm lần nữa như một khoản chi phí độc lập.
- Quà đã trao có thể được tính vào Cost-to-Serve theo giá vốn quà.
- Dữ liệu không xác định được khách hàng không được tự phân bổ vào CLV cá nhân.

### 4. Công thức

**CAC theo kênh**

CAC = Chi phí Marketing của kênh trong kỳ / Số khách hàng mới được quy thuộc kênh đó trong kỳ.

Nguồn quy thuộc khách hàng được xác định từ CRM Lead/Deal liên kết với Contact. Nếu không xác định được nguồn, ghi nhận “Không xác định”.

**Activity-Based Costing**

Cost Driver Rate = Tổng chi phí vận hành của Activity Cost Pool / Tổng Cost Driver tương ứng trong kỳ.

Chi phí nhân sự = Thời gian thực hiện × Chi phí nhân sự mỗi giờ.

Cost-to-Serve = Tổng chi phí hoạt động được phân bổ cho khách hàng.

Không đưa lương vào Activity Cost Pool nếu đã tính riêng từ Employee Cost Rate.

**CLV**

CLV = Tổng giá trị lợi nhuận đóng góp dự kiến trong vòng đời khách hàng, được chiết khấu theo thời gian, trừ CAC.

Tham số cần chốt trong Module Reporting:

- Discount Rate giả định: 10%/năm, có ghi rõ là giả định.
- Kỳ Retention: Quý.
- Thời gian dự báo CLV: 3 năm, giả định.
- Giá trị mua lại và tỷ lệ giữ chân ưu tiên tính từ dữ liệu lịch sử.
- Dữ liệu chưa đủ phải ghi rõ giả định thay vì thể hiện là số liệu thực tế của Hasaki.

### 5. Chống tính trùng Activity Log

- CRM Call Log và HSK Message Log là dữ liệu tương tác nguồn.
- HSK Activity Log là bản ghi phục vụ phân bổ chi phí.
- Một tương tác nguồn chỉ được tạo một hoạt động chi phí tương ứng khi đáp ứng quy tắc tính.
- `source_event_key` dùng để chống tính lại cùng một hoạt động.
- Không cộng thời gian từ CRM Call Log và HSK Activity Log hai lần cho cùng một lượt xử lý.
- Khi cần tính chi phí hội thoại, Activity Log tham chiếu hội thoại nguồn nhưng không sao chép toàn bộ nội dung tin nhắn.



---



## VIII. CHỐT MÔI TRƯỜNG PHÁT TRIỂN

**Frappe:** Sử dụng cùng phiên bản nền đã khôi phục từ snapshot.\
**Database:** MariaDB của Frappe Site hiện có.\
**Timezone nghiệp vụ:** Asia/Ho_Chi_Minh.\
**Tiền tệ:** VND.

**Quy định:**

1. Mỗi thành viên phát triển trên site local riêng.
2. Không cùng sửa trực tiếp một database đang sử dụng làm bản nền.
3. Không ghi đè database người khác khi merge source code.
4. Không dùng file SQL hoặc snapshot làm phương thức merge tính năng.
5. DocType mới phải có định nghĩa trong App.
6. Custom Field cần được xuất bằng fixture hoặc triển khai qua patch phù hợp.
7. Thay đổi dữ liệu có tính di chuyển phải có patch hoặc hướng dẫn tái tạo.
8. Sau khi cập nhật App, chạy migrate và kiểm thử trên bản sao site.
9. Website WordPress local do Nhi quản lý; các thành viên khác không cần truy cập máy Nhi.
10. Nhi cung cấp mẫu request/response, dữ liệu test và kết quả tích hợp để Nghi/Tường sử dụng.

**Lưu ý:** API từ WordPress tới Frappe phải có địa chỉ mà WordPress backend thực sự truy cập được. Nếu WordPress và CRM chạy trong các môi trường Docker/host khác nhau, không mặc định sử dụng `localhost` của trình duyệt làm địa chỉ API.



---



## IX. CHỐT PHẠM VI CODE VÀ GIT MERGE

### 1. Nguyên tắc phân vùng mã nguồn

Tái sử dụng App thực tế đang có. Nếu nhóm dùng chung namespace `hasaki_crm`, phân vùng đề xuất:

| **Thư mục/chức năng**             | **Người phụ trách**              |
| --------------------------------- | -------------------------------- |
| integrations/wordpress            | Nhi                              |
| integrations/woocommerce          | Nhi                              |
| social_inbox/                     | Trâm                             |
| reporting/                        | Tường                            |
| `tests/postman/` và tài liệu A4.7 | Nghi                             |
| Module nghiệp vụ cá nhân          | Giữ nguyên người sở hữu trước đó |

Không yêu cầu tạo lại App chỉ để có cấu trúc thư mục trên.

### 2. Các file dễ xung đột

| **File/nhóm file**                    | **Quy tắc**                                                                 |
| ------------------------------------- | --------------------------------------------------------------------------- |
| hooks.py                              | Không tự ý sửa các hook của người khác; thay đổi phải review phần phụ thuộc |
| patches.txt                           | Mỗi patch có tên duy nhất, không sửa/xóa patch đã chạy                      |
| fixtures/\*.json                      | Chỉ xuất fixture cần thiết, không xuất toàn bộ cấu hình site                |
| DocType JSON/Controller               | Chỉ người sở hữu DocType chủ trì sửa                                        |
| `requirements.txt` / `pyproject.toml` | Không tự nâng phiên bản thư viện chung                                      |
| `README.md` / tài liệu API            | Cập nhật đúng phần phụ trách                                                |
| Database snapshot                     | Không ghi đè snapshot nền trong PR chức năng                                |
| Core Frappe/CRM                       | Không chỉnh sửa trực tiếp                                                   |

### 3. Quy trình GitHub

Repository:[ https://github.com/yennhinguyenuit/hasaki](https://github.com/yennhinguyenuit/hasaki)

Giữ các branch `main`, `nhi`, `nghi`, `tram`, `tuong`.

**Quy trình:**

1. Trước khi phát triển, lấy bản `main` mới nhất đã thống nhất.
2. Làm việc trên branch riêng.
3. Chỉ commit file thuộc phạm vi phụ trách.
4. Nếu thay đổi DocType/API dùng chung, cập nhật Technical Contract trong cùng PR.
5. Push code và tạo Pull Request vào `main`.
6. Kiểm tra thay đổi, xung đột và tác động tới các module khác.
7. Test cài App và migrate trên bản sao site.
8. Chạy lại kịch bản nghiệp vụ liên quan.
9. Chỉ merge khi kiểm thử đạt.

Không cần tạo thêm `develop` nếu nhóm chưa sử dụng. `main` là branch tích hợp ổn định; không push trực tiếp vào `main`.

### 4. Những hành động bị cấm khi merge

- Xóa hoặc đổi tên DocType do người khác sở hữu.
- Đổi `fieldname` đã được module khác sử dụng.
- Tạo `HSK Order` thứ hai dưới tên khác.
- Tạo Contact/Product trùng.
- Commit API Token, Webhook Secret hoặc mật khẩu.
- Merge code không có migration cho thay đổi database.
- Ghi đè `hooks.py`, fixtures hoặc patches mà không kiểm tra.
- Sử dụng snapshot của một thành viên để thay thế toàn bộ database nhóm.
- Xóa dữ liệu nền hoặc dữ liệu demo của thành viên khác để làm sạch môi trường.



---



## X. TEST CASE BẮT BUỘC TRƯỚC KHI MERGE

| **ID** | **Test case**                          | **Kết quả mong đợi**                                    |
| ------ | -------------------------------------- | ------------------------------------------------------- |
| TC01   | Restore site và cài App mới            | CRM hoạt động, dữ liệu cũ được giữ                      |
| TC02   | Gửi Lead Form hợp lệ                   | Tạo đúng một CRM Lead                                   |
| TC03   | Gửi lại Lead Form cùng submission_id   | Không tạo Lead trùng                                    |
| TC04   | WooCommerce tạo đơn                    | Tạo đúng HSK Order và Order Item                        |
| TC05   | WooCommerce cập nhật đơn               | Cập nhật đơn cũ, không tạo đơn mới                      |
| TC06   | Webhook sai chữ ký                     | Từ chối, không ghi dữ liệu                              |
| TC07   | SKU không tồn tại                      | Ghi lỗi, không tạo CRM Product                          |
| TC08   | Khách WooCommerce chưa có Contact      | Lưu thông tin khách vãng lai, không tạo Contact mới     |
| TC09   | Thanh toán thành công                  | Cập nhật Payment một lần                                |
| TC10   | Social Inbox nhận và phản hồi tin nhắn | Có hội thoại, tin nhắn và lịch sử                       |
| TC11   | Gửi lại cùng một tin nhắn              | Không lưu tin nhắn trùng                                |
| TC12   | Hoàn tiền hoặc voucher                 | Không tạo tác động tài chính trùng                      |
| TC13   | Tính CLV/ABC                           | Kết quả đúng theo dữ liệu và công thức kiểm thử         |
| TC14   | Kiểm tra dữ liệu nền                   | Không mất Contact, Product, Lead, Deal hoặc danh mục cũ |
| TC15   | Cài lại source trên site kiểm thử      | DocType, Field, API và báo cáo có thể tái tạo           |

**Điều kiện được merge:** Các test case liên quan phải đạt; không mất dữ liệu nền, không thay đổi API Contract trái quy ước và không có migration chưa được kiểm thử.



---



## XI. PHÂN CÔNG TRÁCH NHIỆM KỸ THUẬT

| **Thành viên** | **Phạm vi chịu trách nhiệm**                                                                                                   | **Không thực hiện**                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| **Nhi**        | WordPress, WooCommerce, API nhận Lead/Order, HSK Integration Event, kiểm thử tích hợp A4.8                                     | Không sửa cấu trúc Order/Payment do Nghi sở hữu; không phát triển Social Inbox |
| **Trâm**       | A4.9.1 Social Inbox, giao diện chat, Social Conversation, Message Log, API gửi/nhận tin nhắn                                   | Không làm WordPress local của Nhi; không tạo lại Master Data                   |
| **Nghi**       | A4.7 REST API/Webhook thực nghiệm; A4.6 đọc và phân tích CRM/Sales Report; quản lý schema Order/Payment theo phân công cá nhân | Không lập trình lại API WordPress hoặc Social Inbox                            |
| **Tường**      | A4.5 CLV/CAC/ABC; HSK Activity Log, dữ liệu chi phí; A4.9.2 Module Reporting                                                   | Không tạo bản sao Order, Product, Contact hoặc Message Log                     |

Các công việc cá nhân được giữ nguyên và không được phân lại trong tài liệu này.



---



## XII. CÁC ĐIỀU KIỆN PHẢI XÁC NHẬN TRƯỚC KHI CODE

Bản Technical Contract này chốt tên và phương án triển khai. Trước khi bắt đầu, nhóm phải đối chiếu các quyết định với source code và database thực tế.

| **Nội dung cần xác nhận**                                                | **Người xác nhận** | **Kết quả**                |
| ------------------------------------------------------------------------ | ------------------ | -------------------------- |
| Site hiện tại hoạt động và Master Data đầy đủ                            | Trâm               | Xác nhận bộ dữ liệu nền    |
| App thực tế đã có, namespace Python và vị trí source code                | Trâm               | Đường dẫn source chính xác |
| HSK Order, Order Item, Payment đã tồn tại hay chưa; field/status thực tế | Nghi               | Schema dùng chung          |
| Endpoint WordPress/WooCommerce và dữ liệu mẫu                            | Nhi                | API Contract A4.8          |
| Social Inbox dùng Facebook thật hay Demo                                 | Trâm               | Phạm vi API A4.9.1         |
| Nguồn doanh thu, chi phí, hoàn tiền và Activity Log                      | Tường              | Data Contract Reporting    |
| App có thể migrate trên site thử nghiệm                                  | Người tạo PR       | Minh chứng migration       |
| Branch cá nhân đã cập nhật từ main                                       | Từng thành viên    | Sẵn sàng phát triển        |

**Nguyên tắc xử lý khác biệt:** Nếu một DocType/field đã tồn tại trên site với tên khác nhưng cùng ý nghĩa, giữ cấu trúc đang được sử dụng, lập bảng ánh xạ tương thích và cập nhật contract. Không tạo một cấu trúc mới chỉ để ép hệ thống theo tài liệu.

Sau khi xác nhận các mục trên, khóa Technical Contract v1.0. Mọi thay đổi về DocType, field dùng chung, API, trạng thái hoặc công thức tài chính phải được cập nhật phiên bản và review trước khi merge.



---



## XIII. KẾT LUẬN CHỐT TRIỂN KHAI

Nhóm thống nhất:

1. Không tạo Master Data mới.
2. Không làm lại hệ thống và dữ liệu nền Trâm đã bàn giao.
3. Không tạo DocType trùng hoặc đổi tên chỉ vì khác cách đặt tên trong tài liệu.
4. Mỗi DocType/API có một người sở hữu chính.
5. WordPress/WooCommerce do Nhi triển khai độc lập.
6. Social Inbox do Trâm triển khai độc lập.
7. REST API thực nghiệm và CRM/Sales Report do Nghi phụ trách.
8. CLV/ABC và Module Reporting do Tường phụ trách.
9. Các module dùng chung một cấu trúc dữ liệu và API Contract.
10. Source code được quản lý bằng branch và Pull Request; không dùng database snapshot để merge chức năng.
11. Mọi thay đổi schema phải có migration và được kiểm thử.
12. Chỉ nghiệm thu tính năng khi hoạt động trên hệ thống Frappe CRM chung và có minh chứng.

**Technical Contract v1.0 là căn cứ cho các thành viên triển khai TASK 2 và kiểm tra Pull Request trước khi tích hợp.**


