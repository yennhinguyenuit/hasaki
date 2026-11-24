# API CONTRACT — A4.8

Phiên bản triển khai theo Technical Contract v1.1; ngày đối chiếu 24/11/2026. Định nghĩa máy đọc: [API_CONTRACT.openapi.json](API_CONTRACT.openapi.json). Namespace thực tế là `hasaki_integration`, không dùng namespace cũ `hasaki_crm.integrations`.

## 1. Quy ước chung

| Mục | Giá trị |
| --- | --- |
| Site | crm.localhost |
| Base URL đã kiểm tra từ PHP/XAMPP | http://127.0.0.1:8000 |
| Header chọn site | X-Frappe-Site-Name: crm.localhost |
| Media type nghiệp vụ | Content-Type: application/json, Accept: application/json |
| Lead endpoint | POST /api/method/hasaki_integration.wordpress.receive_lead |
| Order endpoint | POST /api/method/hasaki_integration.woocommerce.receive_order |
| Cấu trúc response | Frappe bọc kết quả trong message; client đọc body.message |

Hostname http://crm.localhost:8000 chỉ dùng trực tiếp khi máy gọi phân giải được tên này. Endpoint xử lý đồng bộ; không trả 202 để giả định một queue CRM khác đang chạy.

Ví dụ thành công (các ID trong ví dụ là minh họa, không phải secret):

```json
{"message":{"ok":true,"code":"PROCESSED","data":{"lead":"CRM-LEAD-2026-00130","event":"<event_name>"},"idempotent":false}}
```

Request trùng cùng Event đã Processed trả 200 với code ALREADY_PROCESSED, cùng bản ghi, idempotent=true. Delivery mới của cùng Order có thể trả PROCESSED, idempotent=false nhưng data.unchanged=true; đây là một Event giao nhận mới, không phải một Order mới.

## 2. Lead API

### 2.1 Xác thực và quyền

```http
POST /api/method/hasaki_integration.wordpress.receive_lead HTTP/1.1
Host: 127.0.0.1:8000
X-Frappe-Site-Name: crm.localhost
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
Accept: application/json
```

Các phần trong dấu <> là placeholder. User phải có sẵn, enabled, token hợp lệ và có quyền create CRM Lead. Frappe kiểm tra api_key/api_secret trước dispatch; endpoint yêu cầu scheme token, kiểm tra user token trùng session user và quyền create. Cookie-only không đáp ứng contract. Tài khoản local hiện dùng tuvan@hasaki.example; không chép token vào tài liệu, trình duyệt hoặc ảnh demo.

### 2.2 Request

Giới hạn raw body 65.536 byte, JSON object. Các trường dưới đây là allowlist; trường ngoài danh sách bị từ chối. Chuỗi được trim khi validate/lưu; null không thay thế cho chuỗi optional.

| Field | Kiểu | Bắt buộc | Điều kiện / ánh xạ |
| --- | --- | --- | --- |
| submission_id | string | Có | Không rỗng sau trim, tối đa 140; lưu event_id/external_object_id |
| first_name | string | Có | Không rỗng, tối đa 140 → CRM Lead.first_name |
| last_name | string | Không | Tối đa 140, mặc định chuỗi rỗng → last_name |
| phone | string | Có | Tối đa 32; 7–15 chữ số, có thể có + đầu và dấu cách ().- theo regex source → mobile_no |
| email | string | Không | Tối đa 140; chuỗi rỗng được phép, có giá trị phải hợp lệ → email |
| message | string | Có | Không rỗng, tối đa 10.000 → Comment.content đã escape, xuống dòng thành br |
| consent | boolean | Có | Chỉ JSON true; không chấp nhận 1 hoặc chuỗi true |

```json
{
  "submission_id": "demo-lead-20261124-001",
  "first_name": "Khách demo",
  "last_name": "A4.8",
  "phone": "0900000000",
  "email": "demo@example.invalid",
  "message": "Tôi cần tư vấn sản phẩm.\nThông tin dòng thứ hai.",
  "consent": true
}
```

Chuỗi message trong ví dụ dùng escape `\n` của JSON để xuống dòng. Không chèn newline chưa escape trực tiếp vào giữa chuỗi JSON. Các ví dụ chỉ dùng email/số điện thoại test.

Nguồn luôn là CRM Lead Source `Web Form` đã có. Status do controller CRM Lead hiện hữu chọn (site có `New`). Không tự tạo Contact hoặc field consent trên Lead. Điện thoại được giữ theo chuỗi đã trim, chưa chuẩn hóa 0/+84.

### 2.3 Chống trùng và ghi Event

```text
sid = trim(submission_id)
idempotency_key = "wp:lead:" + SHA256(UTF8(sid))
payload_sha256 = SHA256(UTF8(json.dumps(payload,
    sort_keys=True, ensure_ascii=False, separators=(",", ":"))))
```

Canonical JSON bỏ khác biệt thứ tự key/khoảng trắng cấu trúc; **không** tự bỏ khoảng trắng bên trong mọi giá trị chuỗi trước khi hash. Cùng key + cùng hash + Processed → cùng Lead và Event. Cùng key + hash khác → 409. Failed với cùng hash có thể thử lại sau khi sửa điều kiện bên ngoài; sửa nội dung gửi cần submission_id mới, không sửa log để tái sử dụng ID cũ.

Thiếu/sai token hoặc không có submission_id hợp lệ thì chưa tạo Event. Lỗi nội dung sau khi đã nhận ID có thể để lại Event Failed mà không có Lead. Redis lock Event + unique index và commit trong lock bảo vệ request đồng thời. Lead, Comment, Event Processed được commit cùng giao dịch.

## 3. WooCommerce Order API

### 3.1 Xác thực chữ ký

```http
POST /api/method/hasaki_integration.woocommerce.receive_order HTTP/1.1
X-Frappe-Site-Name: crm.localhost
X-WC-Webhook-Source: http://localhost:8080/shopdongho/
X-WC-Webhook-Topic: order.created
X-WC-Webhook-Delivery-ID: <native_delivery_id>
X-WC-Webhook-Signature: <base64_hmac>
Content-Type: application/json
```

```text
signature = base64(HMAC-SHA256(webhook_secret, exact_raw_request_body))
```

Không parse rồi stringify trước khi tính/kiểm tra chữ ký. So sánh constant-time bằng hmac.compare_digest. Source bỏ dấu / cuối và phải khớp khóa cấu hình `hasaki_woocommerce_stores` trong site config. Không suy ra store đáng tin chỉ từ payload. User cấu hình phải có sẵn, enabled, có quyền create/write HSK Order và create HSK Payment. Webhook dùng HMAC, không dùng Guest để bỏ qua các kiểm tra nghiệp vụ.

Source chưa biết/chữ ký sai → 401 INVALID_SIGNATURE, không tạo Event/Order/Payment. Body > 1.048.576 byte bị từ chối. Topic hỗ trợ order.created và order.updated; Delivery-ID 1–100 ký tự theo `[A-Za-z0-9_.-]`.

### 3.2 Payload và mapping

JSON object native WooCommerce, cho phép các trường dư chuẩn của nguồn nhưng chỉ map các trường được liệt kê. Ví dụ rút gọn hợp lệ cho create:

```json
{
  "id": 990001,
  "status": "pending",
  "currency": "VND",
  "date_created_gmt": "2026-11-24T04:00:00",
  "date_modified_gmt": "2026-11-24T04:00:00",
  "date_paid_gmt": null,
  "billing": {
    "first_name": "Khách",
    "last_name": "Demo",
    "phone": "0900000000",
    "email": "demo@example.invalid"
  },
  "line_items": [{"id": 1,"sku": "HSK-96589","quantity": 1,"subtotal": "267000.00","total": "267000.00"}],
  "discount_total": "0.00",
  "shipping_total": "0.00",
  "total": "267000.00",
  "payment_method": "cod",
  "transaction_id": ""
}
```

SKU minh họa đã có trên local; máy khác phải chọn SKU hiện hữu của máy đó. Giá/stock master không được sửa để chạy ví dụ.

| Trường nguồn | Điều kiện / mapping |
| --- | --- |
| id | Integer hoặc chuỗi số nguyên dương 1–20 chữ số, không bool; → external_order_id dạng Data |
| status | Một trạng thái hỗ trợ trong bảng mapping bên dưới |
| currency | VND |
| date_created_gmt | ISO datetime; bắt buộc khi ghi Order → order_date |
| date_modified_gmt | ISO datetime; bắt buộc để so phiên bản → last_source_modified_at |
| date_paid_gmt | Có thể null/rỗng; có giá trị hợp lệ mới là tín hiệu ghi Paid |
| billing | Object, có thể thiếu để dùng object rỗng; first_name/last_name/email tối đa 140, phone tối đa 32; tên ghép tối đa 140 |
| billing.email/phone | Khớp chính xác với Contact.email_id/mobile_no; nhiều/khác kết quả để guest |
| line_items | Array 1–500 dòng; mỗi dòng là object |
| line_items[].id | ID nguyên dương, không trùng trong cùng payload |
| line_items[].sku | Chuỗi bắt buộc, tối đa 140; đối chiếu CRM Product.product_code |
| line_items[].quantity | > 0 và ≤ 1.000.000 → qty |
| line_items[].subtotal / total | Tiền hữu hạn ≥ 0, total ≤ subtotal; → unit_price, discount_amount, line_total |
| discount_total / shipping_total / total | Tiền hữu hạn, 0 đến 9.999.999.999.999,99; số hoặc chuỗi số; → các tổng tiền Order |
| payment_method | Chuỗi tối đa 140; bắt buộc nếu date_paid_gmt có giá trị |
| transaction_id | Chuỗi tùy chọn tối đa 140; dùng đối chiếu Payment đã có |

Datetime không có timezone trong trường _gmt được hiểu là UTC; đổi sang Asia/Ho_Chi_Minh trước khi lưu dạng Datetime không kèm tz. Các giá trị offset ISO hợp lệ cũng được quy đổi theo timezone site.

| WooCommerce.status | HSK Order.status |
| --- | --- |
| pending, on-hold, failed | Pending |
| processing | Processing |
| completed | Completed |
| cancelled | Cancelled |
| refunded | Completed; không tự xác nhận/tạo Refund |

Sản phẩm disabled bị từ chối nếu là dòng mới hoặc đổi sang sản phẩm disabled; dòng đã có cùng product có thể được cập nhật. Không tạo Master Data thiếu. Dòng cùng external_line_id/product giữ cost_price và loyalty_eligible cũ; dòng mới lấy cost từ master và loyalty_eligible=0.

### 3.3 Khóa và phiên bản

```text
order_key = "woo:" + source_store + ":" + str(id)
raw_hash = SHA256(raw_body)
event_hash = SHA256(UTF8(topic + "\n" + str(id) + "\n" + delivery_id + "\n" + raw_hash))
event_key = "woo:event:" + source_store + ":" + event_hash
payment_key = order_key + ":payment"
```

Trong công thức event_hash, `\n` có nghĩa ký tự xuống dòng separator, không phải hai ký tự backslash+n. Việc có thêm topic/id/hash là cần thiết vì Delivery-ID native có thể trùng trong cùng giây. event_id vẫn lưu Delivery-ID; không đặt unique riêng cho event_id.

| Tình huống | Xử lý |
| --- | --- |
| Cùng Event key, đã Processed | 200 ALREADY_PROCESSED, idempotent=true |
| order.created chưa có Order | Tạo một Order theo unique order_key |
| order.created đã có Order | Kiểm tra phiên bản và cập nhật/acknowledge cùng Order |
| order.updated chưa có Order | 409 CONFLICT; giao create thành công rồi phát lại |
| date_modified_gmt cũ hơn | 200 PROCESSED, data.ignored_stale=true; không sửa Order |
| Timestamp bằng và raw hash bằng | 200 PROCESSED, data.unchanged=true |
| Timestamp bằng nhưng hash khác | 409 CONFLICT, giữ bản đang có |
| Nhiều delivery cùng Order | Serialize bằng khóa Order; Event có khóa riêng và DB unique index |

Ví dụ cập nhật xác nhận thanh toán: dùng Order ID đã tạo, status=processing, date_modified_gmt mới hơn, date_paid_gmt hợp lệ và payment_method. Receiver tạo đúng một Payment cho order_key:payment. Nếu tổng tiền hoặc transaction ID/method xung đột Payment đã xác nhận thì rollback và trả 409. Không chỉ đổi status để giả lập Paid khi nguồn không có date_paid_gmt.

### 3.4 Response và activation probe

```json
{"message":{"ok":true,"code":"PROCESSED","data":{"order":"HSK-ORD-2026-00041","event":"<event_name>"},"idempotent":false}}
```

```json
{"message":{"ok":true,"code":"PROCESSED","data":{"order":"HSK-ORD-2026-00041","event":"<new_event_name>","unchanged":true},"idempotent":false}}
```

WooCommerce kiểm tra Delivery URL bằng form-encoded `webhook_id=1`. Receiver nhận đúng trường form webhook_id là số nguyên dương, trả 200 với `{ok:true,code:"WEBHOOK_PROBE",data:{}}` trong message, không ghi nghiệp vụ. Probe không có chữ ký và không đại diện một webhook Order đã xác thực.

## 4. Mã lỗi

```json
{"message":{"ok":false,"code":"CONFLICT","data":{},"error":{"message":"The event key was already used with a different payload"}}}
```

| Code | HTTP | Khi nào |
| --- | --- | --- |
| VALIDATION_ERROR | 400 | Thiếu/sai trường, consent không true, currency/số tiền/dòng hàng sai |
| VALIDATION_ERROR | 413 / 415 | Body quá lớn / không phải media type JSON cho nghiệp vụ |
| UNAUTHORIZED | 401 / 403 | Token thiếu/sai hoặc user thiếu quyền; một số lỗi method do Frappe cũng trả 403 |
| INVALID_SIGNATURE | 401 | Chữ ký sai hoặc source không có cấu hình |
| SKU_NOT_FOUND | 422 | SKU chưa có trong CRM Product |
| CONFLICT | 409 | Key/payload, phiên bản, Payment, config hoặc Order chưa có xung đột; khóa đang bận |
| INTERNAL_ERROR | 500 | Lỗi xử lý ngoài các lỗi nghiệp vụ nhận diện được |

Sai token có thể bị Frappe từ chối trước handler; after_request chuẩn hóa body chỉ cho hai path A4.8. Không áp dụng quy tắc body này cho mọi API của Frappe. GET bị từ chối; test hiện chấp nhận 403/405 theo cách Frappe validate method. Một số lỗi framework/network trước khi chọn được site có thể không đi qua hook của App.

Lỗi nghiệp vụ sau khi tạo Event rollback chứng từ/dòng/Payment rồi lưu Event Failed với error_summary ngắn; không trả traceback hoặc raw customer payload. Lỗi auth/signature trước đó không tạo Integration Event. Nếu request trùng đã Processed nhưng bản ghi đích bị xóa, trả CONFLICT thay vì tự tạo bản thay thế.

## 5. Contract riêng phía WordPress

Public form POST đến wp-admin/admin-post.php với action=hasaki_submit_lead, submission_id UUID, hasaki_nonce, các trường biểu mẫu và consent=1. Đây là form endpoint WordPress, không phải REST endpoint CRM ở trên. Plugin chuyển consent=1 thành JSON true và token chỉ được thêm tại PHP backend.

Thành công redirect 303 với hsk_state=sent. Lỗi gửi/validation từ CRM redirect 303 với hsk_state=error và giữ hsk_submission để retry. Nonce/honeypot/UUID bị từ chối sớm; bucket ≥10 request/phút trả 429 tại WordPress. API CRM tự thân không có rate limit 10/phút được App cài thêm.

Tên cấu hình phía WordPress: HASAKI_CRM_BASE_URL, HASAKI_CRM_API_KEY, HASAKI_CRM_API_SECRET, HASAKI_CRM_SITE, HASAKI_WC_WEBHOOK_SECRET. CRM dùng hasaki_woocommerce_stores gồm source_store/secret/user. Chỉ bàn giao giá trị secret qua kênh riêng; không đưa vào tài liệu hoặc command mẫu đã điền thật.
