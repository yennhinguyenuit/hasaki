# DATA DICTIONARY — A4.8

Ngày đối chiếu: 24/11/2026. Căn cứ: JSON schema trong App, metadata database `crm.localhost`, controller và [DATA_DICTIONARY.json](DATA_DICTIONARY.json). Tất cả thuộc module `Hasaki Integration`, `custom=0`, engine `InnoDB`.

## 1. Danh sách và quan hệ

| DocType | Loại | Định danh | Quan hệ chính |
| --- | --- | --- | --- |
| HSK Order | Document độc lập | HSK-ORD-{YYYY}-{#####} | Contact/Lead/Deal tùy chọn, nhiều Item/History/Payment |
| HSK Order Item | Child Table, istable=1 | Frappe cấp tên dòng | parent=HSK Order, parentfield=items; product → CRM Product |
| HSK Order Status History | Child Table, istable=1 | Frappe cấp tên dòng | parent=HSK Order, parentfield=status_history; changed_by → User |
| HSK Payment | Document độc lập | HSK-PAY-{YYYY}-{#####} | order → HSK Order; một Order có nhiều Payment |
| HSK Integration Event | Document kỹ thuật độc lập | hash | Dynamic Link tới CRM Lead hoặc HSK Order |

`items` và `status_history` là Table Field trong metadata; dữ liệu nằm ở bảng con qua `parent`, không phải cột JSON ở bảng Order. Các Link luôn dùng `name` thật của bản ghi đích. `sku` được đối chiếu với `CRM Product.product_code`.

## 2. Toàn bộ trường nghiệp vụ

“Bắt buộc” trong bảng là `reqd` của JSON; các điều kiện bổ sung được mô tả ở cột ý nghĩa và phần quy tắc. `RO` là read_only trong metadata; không suy rộng rằng mọi field RO đều được chặn sửa bằng mọi API. Các bất biến có kiểm tra trong controller được nêu riêng.


### HSK Order

| Fieldname | Kiểu | Bắt buộc | Default | Options / quan hệ | Thuộc tính | Ý nghĩa / điều kiện |
| --- | --- | --- | --- | --- | --- | --- |
| `customer` | Link | Không | — | Contact | — | Khóa Contact.name hiện hữu; có thể trống với khách vãng lai. |
| `lead` | Link | Không | — | CRM Lead | — | CRM Lead.name hiện hữu; receiver WooCommerce không tự truy tìm hoặc gán Lead. |
| `deal` | Link | Không | — | CRM Deal | — | CRM Deal.name hiện hữu; không tự tạo Deal. |
| `source_channel` | Select | Có | `Manual` | WooCommerce<br>POS<br>Manual | — | Kênh chứng từ; WooCommerce bắt buộc có định danh ngoài. |
| `source_store` | Data | Không | — | — | — | Mã nguồn ổn định; local hiện tại hasaki-local. WooCommerce yêu cầu mã này. |
| `external_order_id` | Data | Không | — | — | — | ID đơn ở nguồn ngoài, lưu dạng Data; WooCommerce yêu cầu. |
| `integration_key` | Data | Không | — | — | Unique + index, RO | WooCommerce: woo:{source_store}:{external_order_id}; POS/Manual cho phép null. |
| `order_date` | Datetime | Có | — | — | — | Thời điểm đặt hàng; API WooCommerce chuyển date_created_gmt sang timezone site. |
| `status` | Select | Có | `Pending` | Pending<br>Processing<br>Shipping<br>Completed<br>Cancelled | — | Giá trị lưu theo Select; không thay bằng nhãn tiếng Việt. |
| `payment_status` | Select | Có | `Pending` | Pending<br>Paid<br>Failed<br>PartiallyRefunded<br>Refunded | RO | Controller tổng hợp từ Payment; đơn mới luôn Pending. |
| `currency` | Data | Có | `VND` | — | — | Chỉ nhận VND trong controller; không tạo Currency/Sales Channel master mới. |
| `grand_total` | Currency | Có | — | — | precision=2 | Tổng phải thanh toán, lấy total từ WooCommerce; không tự tính lại từ dòng hàng. |
| `discount_total` | Currency | Không | `0` | — | precision=2 | Tổng giảm giá để đối soát; không trừ thêm khi line_total đã sau giảm giá. |
| `shipping_total` | Currency | Không | `0` | — | precision=2 | Phí giao hàng lấy shipping_total của nguồn. |
| `guest_full_name` | Data | Không | — | — | — | Họ tên billing, ghép first_name và last_name; vẫn lưu khi đã có Contact. |
| `guest_phone` | Data | Không | — | — | — | Điện thoại billing; không tự chuẩn hóa 0/+84 hoặc tạo Contact. |
| `guest_email` | Data | Không | — | Email | — | Email billing, kiểm tra định dạng khi có giá trị. |
| `items` | Table | Có | — | HSK Order Item | — | Bảng con; ít nhất một dòng. Không phải cột JSON trong tabHSK Order. |
| `status_history` | Table | Không | — | HSK Order Status History | RO | Bảng con do controller quản lý; giữ lại lịch sử đã lưu, append khi đổi status. |
| `last_source_modified_at` | Datetime | Không | — | — | RO | Phiên bản nguồn từ date_modified_gmt, dùng chặn sự kiện cũ. |
| `last_source_payload_sha256` | Data | Không | — | — | RO, length=64 | SHA256 của raw body WooCommerce; dùng đối chiếu phiên bản bằng timestamp. |

### HSK Order Item

| Fieldname | Kiểu | Bắt buộc | Default | Options / quan hệ | Thuộc tính | Ý nghĩa / điều kiện |
| --- | --- | --- | --- | --- | --- | --- |
| `product` | Link | Có | — | CRM Product | — | Link bằng CRM Product.name; không dùng SKU thay cho tên Link nếu hai giá trị khác nhau. |
| `external_line_id` | Data | Không | — | — | — | ID dòng hàng ngoài; duy nhất trong một payload WooCommerce, không unique toàn database. |
| `sku` | Data | Có | — | — | — | Phải bằng product_code của product hiện hữu. |
| `qty` | Float | Có | — | — | precision=6 | Số lượng > 0; WooCommerce giới hạn tối đa 1.000.000, lưu Float precision 6. |
| `unit_price` | Currency | Có | — | — | precision=2 | Đơn giá trước giảm giá; WooCommerce tính subtotal / quantity. |
| `discount_amount` | Currency | Không | `0` | — | precision=2 | Giảm giá toàn dòng, tính subtotal - total; không phải giảm giá mỗi đơn vị. |
| `line_total` | Currency | Có | — | — | precision=2 | Tổng dòng sau giảm giá, lấy line_items[].total; không trừ lại discount_total. |
| `cost_price` | Currency | Không | `0` | — | precision=2 | Snapshot giá vốn đơn vị từ CRM Product.custom_cost_price; giữ khi cùng external_line_id và product được cập nhật. |
| `loyalty_eligible` | Check | Không | `0` | — | — | Cờ dành cho nghiệp vụ Loyalty; receiver giữ giá trị cũ, dòng mới mặc định 0; không tự cộng điểm. |

### HSK Order Status History

| Fieldname | Kiểu | Bắt buộc | Default | Options / quan hệ | Thuộc tính | Ý nghĩa / điều kiện |
| --- | --- | --- | --- | --- | --- | --- |
| `status` | Select | Có | — | Pending<br>Processing<br>Shipping<br>Completed<br>Cancelled | — | Giá trị lưu theo Select; không thay bằng nhãn tiếng Việt. |
| `changed_at` | Datetime | Có | — | — | — | Thời điểm server ghi lịch sử, khác với thời điểm sửa đơn ở nguồn. |
| `changed_by` | Link | Có | — | User | — | User đang xử lý; webhook dùng user hiện hữu trong cấu hình store. |
| `note` | Small Text | Không | — | — | — | Controller ghi Initial status hoặc Status changed. |

### HSK Payment

| Fieldname | Kiểu | Bắt buộc | Default | Options / quan hệ | Thuộc tính | Ý nghĩa / điều kiện |
| --- | --- | --- | --- | --- | --- | --- |
| `order` | Link | Có | — | HSK Order | — | Link HSK Order.name; một Order có thể có nhiều Payment; không đổi order sau khi lưu Payment. |
| `amount` | Currency | Có | — | — | precision=2 | Số tiền >= 0, hữu hạn; chưa phải doanh thu khi status chưa Paid. |
| `payment_method` | Data | Có | — | — | — | Chuỗi phương thức nguồn, ví dụ cod; không tạo Payment Method master. |
| `status` | Select | Có | `Pending` | Pending<br>Paid<br>Failed<br>PartiallyRefunded<br>Refunded | — | Giá trị lưu theo Select; không thay bằng nhãn tiếng Việt. |
| `transaction_id` | Data | Không | — | — | — | Mã giao dịch nguồn, có thể trống; receiver không âm thầm đổi định danh Payment đã xác nhận. |
| `paid_at` | Datetime | Không | — | — | — | Bắt buộc theo controller khi status=Paid; WooCommerce lấy date_paid_gmt. |
| `payment_proof` | Attach | Không | — | — | — | Tệp chứng từ tùy chọn; không được receiver WooCommerce tự tải lên. |
| `payment_integration_key` | Data | Không | — | — | Unique + index, RO | WooCommerce: {Order.integration_key}:payment; bất biến sau lần lưu đầu. |

### HSK Integration Event

| Fieldname | Kiểu | Bắt buộc | Default | Options / quan hệ | Thuộc tính | Ý nghĩa / điều kiện |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | Select | Có | — | WordPress<br>WooCommerce | — | Nguồn sự kiện kỹ thuật WordPress hoặc WooCommerce. |
| `event_id` | Data | Có | — | — | — | WordPress lưu submission_id; WooCommerce lưu Delivery-ID. Riêng event_id không unique. |
| `idempotency_key` | Data | Có | — | — | Unique + index | Khóa chống xử lý lặp có unique index; công thức tại API_CONTRACT.md. |
| `external_object_id` | Data | Có | — | — | — | submission_id của Lead hoặc ID Order ngoài. |
| `event_type` | Data | Có | — | — | — | lead.submitted, order.created hoặc order.updated trong receiver hiện tại. |
| `payload_sha256` | Data | Có | — | — | length=64 | 64 ký tự hex thường; canonical JSON cho Lead, raw body cho WooCommerce. |
| `status` | Select | Có | `Received` | Received<br>Processed<br>Failed | — | Giá trị lưu theo Select; không thay bằng nhãn tiếng Việt. |
| `reference_doctype` | Link | Không | — | DocType | — | Tên DocType đích, hiện tại CRM Lead hoặc HSK Order. |
| `reference_name` | Dynamic Link | Không | — | reference_doctype | — | Dynamic Link dùng options=reference_doctype; tham chiếu bản ghi đã tác động. |
| `processed_at` | Datetime | Không | — | — | — | Thời điểm kết thúc xử lý; cũng được ghi cho Failed. Processed bắt buộc có giá trị này. |
| `error_summary` | Small Text | Không | — | — | — | Mã lỗi và mô tả ngắn đã giới hạn nội dung; không lưu raw payload hoặc credentials. |


## 3. Trường hệ thống Frappe có trong database

Ngoài 53 field nghiệp vụ ở trên, database thực tế còn có các trường dưới đây. Chúng do Frappe quản lý, không khai báo lặp trong JSON của App.

| Fieldname | Kiểu / vai trò | Áp dụng |
| --- | --- | --- |
| name | Data, khóa chính của Document/dòng | Cả 5 DocType |
| creation | Datetime tạo | Cả 5 |
| modified | Datetime sửa | Cả 5 |
| modified_by | User tạo lần sửa gần nhất | Cả 5 |
| owner | User sở hữu bản ghi | Cả 5 |
| docstatus | Int, trạng thái chứng từ nền tảng | Cả 5; không cấu hình is_submittable trong App này |
| idx | Int, thứ tự dòng | Cả 5; đặc biệt quan trọng với Child Table |
| parent | Data, tên Order cha | Item và History |
| parentfield | Data, items hoặc status_history | Item và History |
| parenttype | Data, HSK Order | Item và History |
| _user_tags | Text, nhãn hệ thống | Order, Payment, Integration Event |
| _comments | Text/JSON cache bình luận của Frappe | Order, Payment, Integration Event |
| _assign | Text/JSON giao việc | Order, Payment, Integration Event |
| _liked_by | Text/JSON tương tác | Order, Payment, Integration Event |

`doctype` có trong biểu diễn JSON/Document, không phải cột vật lý của từng bảng này. Message của Lead được lưu ở DocType **Comment** riêng; không nhầm với cache `_comments`.

## 4. Giá trị trạng thái lưu

| Đối tượng | Giá trị |
| --- | --- |
| Order.status và History.status | Pending, Processing, Shipping, Completed, Cancelled |
| Order.payment_status và Payment.status | Pending, Paid, Failed, PartiallyRefunded, Refunded |
| Integration Event.status | Received, Processed, Failed |
| Integration Event.source | WordPress, WooCommerce |
| Order.source_channel | WooCommerce, POS, Manual |

WooCommerce `pending`, `on-hold`, `failed` → Pending; `processing` → Processing; `completed` → Completed; `cancelled` → Cancelled; `refunded` → Completed. Mapping cuối chỉ giữ thông tin đơn bán lịch sử, **không xác nhận hoàn tiền**. Native WooCommerce không có trạng thái Shipping; trạng thái custom chưa có mapping sẽ bị từ chối.

## 5. Quy tắc controller và đồng bộ

1. Currency chỉ VND. Giá trị tiền phải hữu hạn, không âm; qty phải > 0. Giá trị `grand_total` không được controller tự suy ra từ items.
2. WooCommerce bắt buộc source_store/external_order_id; key chuẩn được controller sinh/đối chiếu. Với Order WooCommerce đã lưu, source_channel/source_store/external_order_id/integration_key không được đổi. POS/Manual được có nhiều key null.
3. product và sku phải cùng chỉ một sản phẩm hiện hữu. Receiver không tạo sản phẩm khi thiếu SKU, không tạo Contact khi không khớp. Chỉ gán Contact khi tập kết quả khớp chính xác email_id/mobile_no có đúng một tên; mâu thuẫn hoặc nhiều kết quả thì để guest.
4. Trường cost_price lấy giá vốn đơn vị lúc import; cùng line ID/product thì cập nhật sau không lấy lại giá vốn master. Chi phí dòng phục vụ Reporting thường là qty × cost_price. App chưa tính báo cáo giá vốn/CLV.
5. unit_price = subtotal / qty, discount_amount = subtotal - total, line_total = total. Receiver không import riêng mọi loại tax/fee; grand_total lấy total của nguồn. Không giả định mọi đơn luôn có grand_total = tổng line_total + shipping_total.
6. Lịch sử Order do controller giữ từ database. Dữ liệu client gửi vào status_history không được dùng để thay thế các dòng cũ; thêm một dòng ban đầu và một dòng mỗi lần status đổi.
7. Đơn mới luôn payment_status=Pending. Đổi Order sang Processing không tự tạo Paid. Webhook cần date_paid_gmt có giá trị, trạng thái không phải Pending/Cancelled và payment_method để tạo Payment Paid.
8. Payment.order và payment_integration_key bất biến sau lưu. Paid yêu cầu paid_at. Receiver giữ Payment đã có nếu amount/method/transaction ID không xung đột; không tự đảo trạng thái refund do module khác ghi.
9. Tổng hợp payment_status theo thứ tự thực tế trong payments.py: có PartiallyRefunded → PartiallyRefunded; có Refunded → PartiallyRefunded nếu còn tổng Paid > 0, ngược lại Refunded; có Paid và tổng amount của các Payment Paid ≥ grand_total → Paid; có Payment và tất cả Failed → Failed; còn lại Pending. Trả thiếu một phần tiền vẫn là Pending, không có giá trị PartiallyPaid trong Select.
10. Các khóa Order, Payment và Event có unique index. Redis lock theo Order/Event và transaction/savepoint bảo vệ xử lý lặp; lỗi nghiệp vụ rollback Order/Item/History/Payment, chỉ giữ Event Failed nếu đã tới giai đoạn tạo Event.
11. Event Processed bắt buộc reference_doctype/reference_name/processed_at. Hash phải 64 ký tự hex thường. Không lưu consent thành custom field mới: Processed của Lead chỉ đạt được sau kiểm tra consent=true.

## 6. Permission và dữ liệu nền

| DocType | Quyền hiện tại |
| --- | --- |
| HSK Order / HSK Payment | System Manager, Sales Manager, Sales User, CSKH Hasaki: read/select/create/write/report/print; chỉ System Manager có delete trong JSON |
| Hai Child Table | Không có DocPerm độc lập; kế thừa Order cha |
| HSK Integration Event | System Manager và Sales Manager: read/select; không cho người dùng thông thường create/write/delete theo JSON |
| Guest | Không có CRUD trên ba Document độc lập |

Administrator có quyền đặc biệt của Frappe. Endpoint nội bộ ghi Event với ignore_permissions **sau** xác thực/phân quyền; việc tạo Lead/Order/Payment vẫn đi qua quyền của user hiện hữu. Không có Role mới hoặc fixture master trong App.

Contact, CRM Product, HSK Product Category, User, Role, CRM Lead Source được tái sử dụng. Không thêm các Contact field custom_lead_source, custom_lead_id, custom_first_order_date đã loại bỏ khỏi contract.
