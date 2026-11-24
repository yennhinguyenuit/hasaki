"""Build Vietnamese A4.8 Markdown from checked schemas, source and test evidence."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def load(name):
	return json.loads((DOCS / name).read_text(encoding="utf-8"))


def write(name, content):
	(DOCS / name).write_text(content.strip() + "\n", encoding="utf-8")


def table(headers, rows):
	def cell(value):
		return str(value).replace("|", "\\|").replace("\n", "<br>")
	return "\n".join([
		"| " + " | ".join(headers) + " |",
		"| " + " | ".join("---" for _ in headers) + " |",
		*("| " + " | ".join(cell(v) for v in row) + " |" for row in rows),
	])


FIELD_NOTES = {
	"customer": "Khóa Contact.name hiện hữu; có thể trống với khách vãng lai.",
	"lead": "CRM Lead.name hiện hữu; receiver WooCommerce không tự truy tìm hoặc gán Lead.",
	"deal": "CRM Deal.name hiện hữu; không tự tạo Deal.",
	"source_channel": "Kênh chứng từ; WooCommerce bắt buộc có định danh ngoài.",
	"source_store": "Mã nguồn ổn định; local hiện tại hasaki-local. WooCommerce yêu cầu mã này.",
	"external_order_id": "ID đơn ở nguồn ngoài, lưu dạng Data; WooCommerce yêu cầu.",
	"integration_key": "WooCommerce: woo:{source_store}:{external_order_id}; POS/Manual cho phép null.",
	"order_date": "Thời điểm đặt hàng; API WooCommerce chuyển date_created_gmt sang timezone site.",
	"status": "Giá trị lưu theo Select; không thay bằng nhãn tiếng Việt.",
	"payment_status": "Controller tổng hợp từ Payment; đơn mới luôn Pending.",
	"currency": "Chỉ nhận VND trong controller; không tạo Currency/Sales Channel master mới.",
	"grand_total": "Tổng phải thanh toán, lấy total từ WooCommerce; không tự tính lại từ dòng hàng.",
	"discount_total": "Tổng giảm giá để đối soát; không trừ thêm khi line_total đã sau giảm giá.",
	"shipping_total": "Phí giao hàng lấy shipping_total của nguồn.",
	"guest_full_name": "Họ tên billing, ghép first_name và last_name; vẫn lưu khi đã có Contact.",
	"guest_phone": "Điện thoại billing; không tự chuẩn hóa 0/+84 hoặc tạo Contact.",
	"guest_email": "Email billing, kiểm tra định dạng khi có giá trị.",
	"items": "Bảng con; ít nhất một dòng. Không phải cột JSON trong tabHSK Order.",
	"status_history": "Bảng con do controller quản lý; giữ lại lịch sử đã lưu, append khi đổi status.",
	"last_source_modified_at": "Phiên bản nguồn từ date_modified_gmt, dùng chặn sự kiện cũ.",
	"last_source_payload_sha256": "SHA256 của raw body WooCommerce; dùng đối chiếu phiên bản bằng timestamp.",
	"product": "Link bằng CRM Product.name; không dùng SKU thay cho tên Link nếu hai giá trị khác nhau.",
	"external_line_id": "ID dòng hàng ngoài; duy nhất trong một payload WooCommerce, không unique toàn database.",
	"sku": "Phải bằng product_code của product hiện hữu.",
	"qty": "Số lượng > 0; WooCommerce giới hạn tối đa 1.000.000, lưu Float precision 6.",
	"unit_price": "Đơn giá trước giảm giá; WooCommerce tính subtotal / quantity.",
	"discount_amount": "Giảm giá toàn dòng, tính subtotal - total; không phải giảm giá mỗi đơn vị.",
	"line_total": "Tổng dòng sau giảm giá, lấy line_items[].total; không trừ lại discount_total.",
	"cost_price": "Snapshot giá vốn đơn vị từ CRM Product.custom_cost_price; giữ khi cùng external_line_id và product được cập nhật.",
	"loyalty_eligible": "Cờ dành cho nghiệp vụ Loyalty; receiver giữ giá trị cũ, dòng mới mặc định 0; không tự cộng điểm.",
	"changed_at": "Thời điểm server ghi lịch sử, khác với thời điểm sửa đơn ở nguồn.",
	"changed_by": "User đang xử lý; webhook dùng user hiện hữu trong cấu hình store.",
	"note": "Controller ghi Initial status hoặc Status changed.",
	"order": "Link HSK Order.name; một Order có thể có nhiều Payment; không đổi order sau khi lưu Payment.",
	"amount": "Số tiền >= 0, hữu hạn; chưa phải doanh thu khi status chưa Paid.",
	"payment_method": "Chuỗi phương thức nguồn, ví dụ cod; không tạo Payment Method master.",
	"transaction_id": "Mã giao dịch nguồn, có thể trống; receiver không âm thầm đổi định danh Payment đã xác nhận.",
	"paid_at": "Bắt buộc theo controller khi status=Paid; WooCommerce lấy date_paid_gmt.",
	"payment_proof": "Tệp chứng từ tùy chọn; không được receiver WooCommerce tự tải lên.",
	"payment_integration_key": "WooCommerce: {Order.integration_key}:payment; bất biến sau lần lưu đầu.",
	"source": "Nguồn sự kiện kỹ thuật WordPress hoặc WooCommerce.",
	"event_id": "WordPress lưu submission_id; WooCommerce lưu Delivery-ID. Riêng event_id không unique.",
	"idempotency_key": "Khóa chống xử lý lặp có unique index; công thức tại API_CONTRACT.md.",
	"external_object_id": "submission_id của Lead hoặc ID Order ngoài.",
	"event_type": "lead.submitted, order.created hoặc order.updated trong receiver hiện tại.",
	"payload_sha256": "64 ký tự hex thường; canonical JSON cho Lead, raw body cho WooCommerce.",
	"reference_doctype": "Tên DocType đích, hiện tại CRM Lead hoặc HSK Order.",
	"reference_name": "Dynamic Link dùng options=reference_doctype; tham chiếu bản ghi đã tác động.",
	"processed_at": "Thời điểm kết thúc xử lý; cũng được ghi cho Failed. Processed bắt buộc có giá trị này.",
	"error_summary": "Mã lỗi và mô tả ngắn đã giới hạn nội dung; không lưu raw payload hoặc credentials.",
}


TEST_DETAILS = {
	"test_concurrent_duplicate_submission": ("Gửi 4 POST đồng thời cùng submission_id và payload.", "Cả 4 trả 200; một Lead, một lần idempotent=false."),
	"test_consent_requires_boolean": ("Gửi consent lần lượt là chuỗi true, số 1, chuỗi 1 và null.", "Tất cả trả 400; chỉ JSON boolean true được nhận."),
	"test_duplicate_submission_returns_original_lead": ("POST hợp lệ hai lần với cùng submission_id.", "Lần sau 200, idempotent=true và cùng data.lead/data.event."),
	"test_false_consent_rejected_and_logged": ("Gửi consent=false với submission_id hợp lệ.", "400 VALIDATION_ERROR; Event Failed, không có Lead tham chiếu."),
	"test_get_is_not_allowed": ("Gọi GET vào receive_lead.", "Bị từ chối 403 hoặc 405 theo Frappe; không được dùng GET để tạo Lead."),
	"test_html_message_is_safe": ("Gửi message chứa script và thẻ HTML.", "Comment không chứa thẻ script thực thi; nội dung tư vấn còn được lưu."),
	"test_invalid_email_and_phone": ("Thử email sai, phone chứa chữ và phone quá ngắn.", "Các request trả 400."),
	"test_invalid_token_rejected_without_event": ("Gửi API Token không hợp lệ.", "401 UNAUTHORIZED; không có Integration Event cho submission."),
	"test_missing_fields_do_not_create_lead": ("Bỏ lần lượt submission_id, first_name, phone, message.", "400; tổng số Lead không tăng."),
	"test_no_token_rejected_without_event": ("Không gửi Authorization.", "401 UNAUTHORIZED; không có Event."),
	"test_optional_fields_can_be_omitted": ("Không gửi last_name và email.", "200 và ok=true."),
	"test_reused_key_with_different_payload_conflicts": ("Sau request thành công, đổi message nhưng giữ submission_id.", "409 CONFLICT; không tạo Lead thứ hai."),
	"test_valid_lead_mapping_and_comment": ("Gửi đủ 7 trường hợp lệ và đọc trực tiếp database.", "Tên/email/mobile_no/source đúng; đúng một Comment; Event Processed liên kết đúng Lead."),
	"test_activation_probe_writes_no_business_data": ("POST form-encoded webhook_id dương không có chữ ký.", "200 WEBHOOK_PROBE; không tạo Order."),
	"test_bad_signature_has_no_event_or_order": ("Gửi payload với chữ ký HMAC sai.", "401 INVALID_SIGNATURE; không có Order hoặc Event."),
	"test_concurrent_duplicate_delivery": ("Gửi 4 webhook đồng thời cùng delivery/payload.", "200; cùng một Order và chỉ một lần xử lý mới."),
	"test_confirmed_payment_created_once": ("Gửi date_paid_gmt hợp lệ, phát lại và gửi phiên bản mới.", "Chỉ một Payment Paid; amount/paid_at đúng, Order.payment_status=Paid."),
	"test_create_order_items_cost_snapshot_and_guest": ("Gửi order.created có SKU hiện hữu và khách chưa khớp.", "Order/Item đúng, snapshot cost đúng, GMT chuyển +07, guest được lưu, chưa có Payment."),
	"test_duplicate_delivery_returns_same_order": ("Gửi lại cùng delivery/payload.", "idempotent=true; cùng Order, không thêm status history."),
	"test_duplicate_line_ids_rejected": ("Hai line_items dùng cùng id.", "400 và không tạo Order."),
	"test_equal_timestamp_different_payload_conflicts": ("Giữ date_modified_gmt nhưng đổi status/payload.", "409; Order giữ status ban đầu."),
	"test_invalid_money_and_currency_rejected": ("Thử NaN, Infinity, tiền âm và currency USD.", "400; chỉ tiền hữu hạn không âm, currency VND được nhận."),
	"test_invalid_second_line_rolls_back_entire_order": ("Dòng đầu hợp lệ, dòng hai có SKU không tồn tại.", "422; toàn Order được rollback, không lưu dở dòng đầu."),
	"test_missing_order_update_does_not_create_order": ("order.updated cho ID chưa có Order.", "409; không upsert Order thiếu."),
	"test_payment_conflict_rolls_back_order_and_history": ("Sau Paid, thay amount tổng và status trong phiên bản mới.", "409; grand_total/status/history cũ và đúng một Payment được giữ."),
	"test_same_native_delivery_id_can_deliver_different_orders": ("Hai Order khác nhau dùng cùng Delivery-ID.", "Cả hai 200 và có hai mã Order khác nhau."),
	"test_same_native_delivery_id_can_deliver_newer_order_version": ("Cùng Delivery-ID nhưng gửi topic/version cập nhật mới hơn.", "200; cập nhật cùng Order sang Processing."),
	"test_stale_event_cannot_overwrite_order": ("Sau phiên bản mới, gửi phiên bản có date_modified_gmt cũ.", "200 với ignored_stale=true; status/history hiện tại không bị ghi đè."),
	"test_unknown_sku_fails_without_product_creation": ("Gửi SKU chưa có trong CRM Product.", "422 SKU_NOT_FOUND, Event Failed, không có Order; master hash được kiểm tra ở cuối suite."),
	"test_unknown_source_rejected": ("X-WC-Webhook-Source không được cấu hình.", "401 INVALID_SIGNATURE và không có Order."),
	"test_update_existing_order_and_history_without_automatic_payment": ("Tạo Pending rồi gửi Processing mới hơn, không có date_paid_gmt.", "Cùng một Order, thêm đúng lịch sử Processing; Payment vẫn chưa có và payment_status=Pending."),
	"test_five_doctypes_match_source": ("So sánh metadata site với cả 5 JSON schema.", "Module/custom/istable và fieldtype/options/unique/reqd khớp."),
	"test_guest_permissions_and_event_read_only": ("Kiểm tra Guest CRUD và quyền Event của manager hiện hữu.", "Guest bị từ chối; manager đọc được Event nhưng không được tạo Event."),
	"test_history_cannot_be_overwritten_from_resource_api_data": ("Xóa status_history trong dữ liệu Document rồi đổi status và save.", "Controller phục hồi dòng cũ và append dòng mới. Đây là test controller, không phải một request Resource API qua HTTP."),
	"test_manual_orders_allow_multiple_empty_integration_keys": ("Tạo hai Order Manual có integration_key trống.", "Hai Order khác tên, cùng được chấp nhận với key null."),
	"test_multiple_payments_aggregate_and_paid_at_required": ("Order 100.000, thêm Payment Paid 40.000 rồi 60.000; thử Paid thiếu paid_at.", "Order lần lượt Pending rồi Paid; Paid thiếu paid_at bị từ chối."),
	"test_unique_indexes_exist_in_database": ("SHOW INDEX trên Order, Payment, Integration Event.", "Có unique index tương ứng integration_key, payment_integration_key, idempotency_key."),
}


def build_dictionary(schemas):
	parts = ["""
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
"""]
	for schema in schemas:
		parts.append(f"\n### {schema['name']}\n")
		rows = []
		for f in schema["fields"]:
			properties = []
			if f.get("unique"):
				properties.append("Unique + index")
			if f.get("read_only"):
				properties.append("RO")
			if f.get("precision"):
				properties.append("precision=" + f["precision"])
			if f.get("length"):
				properties.append("length=" + str(f["length"]))
			rows.append([f"`{f['fieldname']}`", f["fieldtype"], "Có" if f.get("reqd") else "Không",
				f"`{f['default']}`" if "default" in f else "—", f.get("options", "—"), ", ".join(properties) or "—",
				FIELD_NOTES[f["fieldname"]]])
		parts.append(table(["Fieldname", "Kiểu", "Bắt buộc", "Default", "Options / quan hệ", "Thuộc tính", "Ý nghĩa / điều kiện"], rows))
	parts.append("""

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
""")
	write("DATA_DICTIONARY.md", "\n".join(parts))


def build_tests():
	parts = ["""
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
"""]
	index = 0
	for key, title, source in (
		("lead", "2. Lead API — 13 test case", "hasaki_integration/tests/test_integration_http.py"),
		("woocommerce", "3. WooCommerce API — 18 test case", "hasaki_integration/tests/test_integration_http.py"),
		("schema", "4. Schema/controller — 6 test case", "hasaki_integration/tests/test_schema.py"),
	):
		report = load(f"test_results_{key}.json")
		parts.append(f"\n## {title}\n\nLần chạy ghi nhận: **{report['checked_at']}** (giờ site). Source: `{source}`.\n")
		for entry in report["results"]:
			index += 1
			method = entry["test"].split(".")[-1]
			steps, expected = TEST_DETAILS[method]
			parts.append(f"\n### TC{index:02d} — {method}\n\n- Thao tác: {steps}\n- Kỳ vọng và kiểm tra thực tế: {expected}\n- Kết quả: **{entry['status']}**.\n")
	assert index == 37
	cron = load("test_results_wp_cron.json")
	parts.append(f"""
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

Kết quả **{cron['status']}**, quan sát tổng cộng **{cron['elapsed_seconds']} giây**. Đơn WordPress **{cron['wordpress_order_id']}** → **{cron['crm_order']}**, Payment test **{cron['crm_payment']}**.

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

Test tự nhiên trên Windows: `python scripts/test_wp_cron.py`. Script tạo thêm đơn test và chỉ truy cập trang chủ, chờ tối đa 180 giây mỗi pha. Test doubles PHP: `D:\\baitap\\php\\php.exe scripts/test_wordpress_bridge.php`.

Không gọi tên hàm test không tồn tại, không chạy Frappe fixture runner thay cho các lệnh trên, không gán Passed nếu script timeout/Failed. Xem [HANDOVER.md](HANDOVER.md) về điều kiện môi trường và quyền.
""")
	write("TEST_REPORT.md", "\n".join(parts))


def build_implementation():
	status = load("IMPLEMENTATION_STATUS.json")
	cron = load("test_results_wp_cron.json")
	manifest = []
	for folder in ("hasaki_integration/hasaki_integration/doctype", "wordpress-plugin", "scripts"):
		for path in sorted((ROOT / folder).rglob("*")):
			if path.is_file() and "__pycache__" not in path.parts:
				manifest.append([f"`{path.relative_to(ROOT).as_posix()}`", "Tạo mới trong A4.8"])
	for name in ("a48_preflight.py", "a48_verify.py", "integration.py", "local_setup.py", "payments.py", "validation.py", "wordpress.py", "woocommerce.py", "tests/__init__.py", "tests/test_integration_http.py", "tests/test_schema.py"):
		manifest.append([f"`hasaki_integration/{name}`", "Tạo mới trong A4.8; helper test/audit được bổ sung khi tổng kết"])
	manifest.extend([["`README.md`", "Chỉnh sửa mô tả App, triển khai và kết quả"], ["`hasaki_integration/hooks.py`", "Thêm required_apps và after_request có phạm vi endpoint"]])
	write("IMPLEMENTATION_REPORT.md", f"""
# IMPLEMENTATION REPORT — A4.8

## 1. Kết quả và căn cứ nghiệm thu

Ngày tổng kết **24/11/2026**. Source triển khai bám Technical Contract v1.1; phụ lục được ưu tiên. Căn cứ gồm source trong App, metadata MariaDB đọc lại và kết quả test thật. Không coi tài liệu thiết kế là bằng chứng tính năng đã chạy.

- Đủ 5 DocType có JSON/controller/permission, hai Child Table và ba unique index. Backup trước migrate; migrate crm.localhost thành công.
- Lead Form WordPress → API Token → CRM Lead/Comment/Event đã chạy trên website thật.
- WooCommerce native order.created/order.updated → HMAC → Order/Item/History/Payment/Event đã chạy; có chống trùng và phiên bản cũ.
- **37/37 test case Passed**: 13 Lead, 18 WooCommerce, 6 schema/controller. Xem [TEST_REPORT.md](TEST_REPORT.md).
- WP-Cron tự động **{cron['status']}**: đơn {cron['wordpress_order_id']} → {cron['crm_order']}, Payment test {cron['crm_payment']}; không chạy action thủ công. Quan sát {cron['elapsed_seconds']} giây, không thay cho soak test dài hạn.
- 200 SKU WordPress khớp 200 CRM Product. Bản ghi và metadata sản phẩm, file/theme đang dùng và các plugin cũ được bảo toàn.

## 2. Môi trường thực tế

| Thành phần | Giá trị xác nhận |
| --- | --- |
| App | hasaki_integration 0.0.1, module Hasaki Integration |
| Site / Container | crm.localhost / crm-frappe-1 |
| Frappe / CRM | 15.127.1 / 1.92.0 |
| Source Windows | C:\\Users\\Yen Nhi\\frappe-crm\\hasaki_integration |
| Source Docker | /workspace/hasaki_integration |
| Bench | /home/frappe/frappe-bench; apps/hasaki_integration liên kết source mount |
| Database CRM / cache | MariaDB hiện hữu; Redis dùng khóa và dịch vụ nền |
| XAMPP | D:\\baitap; Apache port 8080; PHP 8.2.12 |
| WordPress | 7.1.5, D:\\baitap\\htdocs\\shopdongho |
| WooCommerce | 10.9.4; tiền tệ VND |
| URL website | http://localhost:8080/shopdongho/ |
| WordPress database / theme | shopdongho / flatsome-hasaki-child (parent flatsome) |
| Backend WordPress → CRM | http://127.0.0.1:8000 + X-Frappe-Site-Name: crm.localhost |
| Timezone dữ liệu CRM | Asia/Ho_Chi_Minh; UTC nguồn được đổi trước khi lưu Datetime |

Đường dẫn C:\\xampp ban đầu không tồn tại trên máy. Website đã được nhận diện từ Apache đang chạy ở D:\\baitap, sau đó kiểm tra blogname/theme/database trước khi cấu hình. crm.localhost chưa phân giải trên Windows tại lần kiểm tra; địa chỉ loopback + site header đã ping và tích hợp thành công. Không sửa hosts để đạt kết quả này.

## 3. Kiến trúc

```mermaid
flowchart LR
    Visitor[Người dùng] --> Form[Form trong hộp hỗ trợ WordPress]
    Form --> PHP[Hasaki CRM Bridge / PHP backend]
    PHP -->|API Token, JSON| Lead[wordpress.receive_lead]
    Lead --> LeadDB[CRM Lead + Comment + Integration Event]
    Woo[WooCommerce Order] --> Queue[Action Scheduler]
    Traffic[Lượt truy cập website] --> Cron[WP-Cron tự nhiên]
    Cron --> Queue
    Queue -->|Native webhook, raw JSON + HMAC| Receiver[woocommerce.receive_order]
    Receiver --> OrderDB[HSK Order + Item + History + Payment + Event]
    Lead --> Lock[Redis locks + DB unique keys + transaction]
    Receiver --> Lock
```

REST xử lý nghiệp vụ đồng bộ trong transaction phía Frappe. Queue phát webhook ở **WordPress**, không phải một scheduler do App CRM tạo. after_request hook chỉ chuẩn hóa lỗi của hai endpoint Hasaki; không thay response của API CRM khác. App yêu cầu CRM qua required_apps, không có fixture tạo Master Data và không có custom Event Bus.

## 4. Chức năng đã triển khai

### 4.1 Lead

Nhận submission_id, first_name, last_name, phone, email, message, consent. Nguồn Web Form phải có sẵn. phone → mobile_no; message được escape và lưu Comment liên kết Lead. consent phải JSON true, không tạo Contact, không thêm custom field Contact. Native Frappe xác thực token trước dispatch; endpoint còn bắt buộc scheme token và quyền create CRM Lead. submission_id chống gửi lặp qua Event và hash canonical JSON.

Plugin dùng nonce, honeypot, giới hạn 10 lần/phút theo bucket IP đã hash, giữ submission ID khi retry và gửi token từ PHP. Retry tối đa một lần cho lỗi truyền/HTTP 5xx với nguyên body. Form gắn vào hsk-support qua plugin footer hook, không sửa theme.

### 4.2 Order/Payment

HMAC-SHA256 raw body, so khớp source store đã cấu hình. SKU bắt buộc tồn tại; Contact được đối chiếu chính xác nếu duy nhất, nếu không giữ guest. Order key woo:store:id; Payment key thêm :payment. Status history do controller giữ; cost_price snapshot theo dòng. Processing không chứng minh Paid nếu thiếu date_paid_gmt.

Event key WooCommerce có cả topic/order ID/Delivery-ID/raw hash để tránh Delivery-ID native trùng trong cùng giây. Sự kiện cũ được acknowledge ignored_stale; cùng timestamp khác hash trả 409. update cho Order chưa tồn tại trả 409 và cần giao lại sau create. Không có retry queue CRM riêng để tự phát lại mọi lỗi.

### 4.3 WP-Cron

Site không bật DISABLE_WP_CRON; action_scheduler_run_queue có interval 60. Bài test mới chỉ tạo/cập nhật giao dịch và GET trang chủ; log action ghi context WP Cron, Apache ghi loopback wp-cron.php 200 tự sinh. Cả pha Pending và Processing/Paid đã tự giao thành công. Không sửa cron core hoặc cấu hình lại scheduler của site.

## 5. Các mốc và dữ liệu minh chứng

| Luồng | WordPress | CRM | Minh chứng |
| --- | --- | --- | --- |
| Form thật | submission trong JSON E2E | CRM-LEAD-2026-00130 + một Comment | test_results_wordpress_e2e.json |
| Native webhook, action được chạy có kiểm soát trước đây | Order 1943 | HSK-ORD-2026-00041 / HSK-PAY-2026-00042 | test_results_woocommerce_e2e.json |
| Native webhook, WP-Cron tự nhiên | Order {cron['wordpress_order_id']} | {cron['crm_order']} / {cron['crm_payment']} | test_results_wp_cron.json |

Payment trong hai luồng trên là xác nhận **test** từ date_paid_gmt; không gọi cổng thanh toán hay thu tiền thật. Giao dịch test được giữ để kiểm tra. Mốc tổng số Document lúc xuất IMPLEMENTATION_STATUS.json: {', '.join(f'{key}={value}' for key, value in status['transaction_counts'].items())}; số lượng có thể tăng nếu demo/test lại.

## 6. Backup và thay đổi ngoài App

- CRM trước migrate: sites/crm.localhost/private/backups/20261124_112115-crm_localhost-database.sql.gz và site_config_backup tương ứng. Có thêm backup trước cấu hình token ngày 24/11 lúc 11:43.
- WordPress trước thay đổi: C:\\Users\\Yen Nhi\\frappe-crm-backups\\wordpress-a48-20261124, có SQL, wp-config.php và baseline hash; không restore/import.
- Cài file plugin vào wp-content/plugins/hasaki-crm-bridge/hasaki-crm-bridge.php và activate, giữ các plugin trước đó.
- wp-config.php chỉ thêm include có kiểm tra file tồn tại. Credentials ở file riêng ngoài webroot/repository; tài liệu chỉ nêu tên cấu hình, không chứa giá trị.
- Site config CRM thêm source store hasaki-local; cấp/reuse API Token cho user hiện hữu tuvan@hasaki.example, không tạo User hoặc Role mới. WooCommerce có hai webhook Active ID 1/2.
- Không tạo lại App/site/container, không sửa core Frappe/CRM/WordPress/WooCommerce, không sửa BeautyMatch, không push/merge GitHub.

## 7. Danh sách file source tạo/chỉnh sửa

{table(['File tương đối từ root App', 'Thay đổi'], manifest)}

Các file scaffolding __init__.py/modules.txt/patches.txt có sẵn được tái sử dụng nếu không liệt kê là file mới. TECHNICAL_CONTRACT.md do người dùng bổ sung, không phải tài liệu tự sửa nội dung. Các thay đổi .gitignore/.gitattributes đã có trước khi bắt đầu; không nhận là phần triển khai mới.

## 8. Tài liệu và artifact

Sáu Markdown: [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md), [DATA_DICTIONARY.md](DATA_DICTIONARY.md), [API_CONTRACT.md](API_CONTRACT.md), [TEST_REPORT.md](TEST_REPORT.md), [DEMO_GUIDE.md](DEMO_GUIDE.md), [HANDOVER.md](HANDOVER.md).

JSON bằng chứng: DATA_DICTIONARY.json, API_CONTRACT.openapi.json, IMPLEMENTATION_STATUS.json, a48_preflight.json (lịch sử trước triển khai), a48_site_metadata.json, documentation_audit.json, documentation_validation.json, test_results_lead.json, test_results_woocommerce.json, test_results_schema.json, test_results_wordpress_e2e.json, test_results_woocommerce_e2e.json, test_results_woo_native_create.json, test_results_woo_native_update.json, test_results_woo_native_replay.json, test_results_wp_cron.json, wordpress_site_inventory.json, wordpress_preservation.json, wordpress_catalog_compatibility.json. Tên native_create hiện lưu mode resume-created của lần phát lại thành công; không diễn giải là một lần clean create mới.

## 9. Phạm vi bàn giao

Nhi tạm sở hữu 5 schema theo phụ lục v1.1 trên local; nhóm cần rà soát sở hữu trước merge. Loyalty, Refund, Voucher và Reporting chỉ nhận interface hướng dẫn trong HANDOVER; chưa có nghiệp vụ các module này trong App. Không khẳng định đã clean-install ở máy khác, đã thu/hoàn tiền thật, hay đã soak-test WP-Cron nhiều giờ/ngày. Các giới hạn và test chưa thực hiện nằm trong TEST_REPORT.
""")


def build_api():
	write("API_CONTRACT.md", r"""
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
""")


def build_demo():
	cron = load("test_results_wp_cron.json")
	write("DEMO_GUIDE.md", f"""
# DEMO GUIDE — A4.8

## 1. Chuẩn bị phiên demo

1. Mở XAMPP hiện hữu ở D:\\baitap; xác nhận Apache port 8080 và MySQL đang chạy. Không tạo WordPress mới.
2. Trong thư mục App trên Windows, chạy `docker ps`; cần crm-frappe-1, crm-mariadb-1, crm-redis-1 hoạt động. Không chạy restore/reinstall/drop-site để chuẩn bị demo.
3. Mở http://localhost:8080/shopdongho/ và đăng nhập WordPress bằng tài khoản admin hiện hữu ở /wp-admin/. Mở site CRM hiện hữu và đăng nhập tài khoản có quyền xem Lead/Order/Payment/Event. Trên Windows có thể dùng http://127.0.0.1:8000 khi site mặc định đã được cấu hình; backend luôn dùng site header crm.localhost.
4. Chuẩn bị tên test riêng, ví dụ A4.8 DEMO + giờ demo. Không dùng dữ liệu cá nhân thật. Không mở file cấu hình secrets khi quay/chụp màn hình.
5. Kiểm tra plugin Hasaki CRM Bridge Active. WooCommerce → Settings → Advanced → Webhooks: ID 1 order.created và ID 2 order.updated Active, đúng Delivery URL. Không hiển thị nội dung Secret.

Các mã mẫu có sẵn: Lead **CRM-LEAD-2026-00130**; Order WordPress **1943** → **HSK-ORD-2026-00041**, Payment **HSK-PAY-2026-00042**. Bài cron mới: WordPress **{cron['wordpress_order_id']}** → **{cron['crm_order']}**, Payment **{cron['crm_payment']}**. Có thể demo chỉ đọc các bản ghi này để không tạo thêm giao dịch.

## 2. Demo Lead Form từ giao diện

1. Tại trang chủ, kéo xuống footer và bấm **Gửi yêu cầu hỗ trợ**. Hộp hsk-support phải có form Tên/Họ/Điện thoại/Email/Nội dung tư vấn/consent.
2. Nhập Tên A4.8 DEMO, Họ Khách thử, phone 0900000000, email demo@example.invalid, message hai dòng tiếng Việt. Tick đồng ý cung cấp thông tin.
3. Bấm Gửi yêu cầu tư vấn. Quan sát redirect và thông báo đã tiếp nhận. Không cần và không được đưa API Token vào JavaScript trình duyệt.
4. Trong CRM Leads, tìm theo tên và thời điểm vừa gửi, mở Lead. Đối chiếu first_name/last_name/mobile_no/email, source Web Form, Comment có message và đúng tiếng Việt.
5. Trong Frappe Desk dùng thanh tìm kiếm DocType HSK Integration Event; mở Event source WordPress, event_type lead.submitted, reference_name trỏ Lead vừa tạo, status Processed. submission_id nằm ở event_id/external_object_id.
6. Chứng minh chống trùng bằng đúng cùng request/submission_id, không bằng cách refresh rồi điền một form UUID mới. Cách đã kiểm thử sẵn: `python scripts/test_existing_wordpress.py` tạo một Lead test và gửi lại cùng POST. Báo cáo phải cho một Lead/một Comment. Chạy script này tạo thêm giao dịch test.
7. Với consent bỏ chọn, browser có thể chặn submit ngay do required. Backend cũng từ chối false; xem test case TC02/TC04 và báo cáo form E2E. Không sửa browser/source để ép consent vào dữ liệu khách thật.

## 3. Demo WooCommerce với dữ liệu mẫu có sẵn

1. WordPress → WooCommerce → Orders → mở order 1943 hoặc {cron['wordpress_order_id']}. Đây là giao dịch test có created_via a48-integration-test, không phải đơn cần giao thật.
2. Quan sát ID, trạng thái, SKU, số lượng, tổng tiền, thông tin guest. Không chỉnh giá, stock hoặc sản phẩm để demo.
3. Trong Desk mở HSK Order bằng tên tương ứng. Kiểm tra source_channel WooCommerce, source_store hasaki-local, external_order_id, integration_key và bảng items.
4. Đối chiếu SKU/product Link, qty, unit_price, line_total, cost_price, status_history Pending → Processing. Với guest không khớp, customer để trống và guest_* có thông tin.
5. Mở HSK Payment theo order. Đối chiếu Paid, amount, paid_at, transaction_id test và payment_integration_key. Chỉ một Payment được ghi dù đã phát lại webhook.
6. Mở HSK Integration Event lọc source WooCommerce và external_object_id đúng ID. Phân biệt event nhận mới với một Order/Payment đã có; nhiều Event không có nghĩa nhiều đơn.

## 4. Demo webhook tự động, không bấm Run

Chọn một trong hai cách sau. Cách A chỉ đọc bằng chứng, cách B tạo một đơn test mới với guard bảo toàn stock/sales/email.

### Cách A — mở bằng chứng đã có

Mở [test_results_wp_cron.json](test_results_wp_cron.json), WooCommerce → Status → Scheduled Actions và tìm action IDs **1985, 1986, 1988**. Mở Logs, chỉ ra “started via WP Cron” và “complete via WP Cron”. Đối chiếu Order {cron['wordpress_order_id']} cùng CRM Order/Payment. Không bấm Run hoặc gọi process_action để chứng minh bài này.

### Cách B — chạy mới luồng tự nhiên

Tại thư mục App trên Windows:

```powershell
python scripts/test_wp_cron.py
```

Script dùng PHP XAMPP tạo một Order test từ sản phẩm hiện hữu; WooCommerce tự enqueue ở shutdown. Script chỉ GET trang chủ, quan sát queue và CRM, sau đó cập nhật date_paid_gmt test rồi chờ giao tự động. Không gọi wp-cron.php trực tiếp. Mỗi pha chờ tối đa 180 giây; đọc status thật trong docs/test_results_wp_cron.json, không gán Passed nếu timeout.

Nếu muốn thao tác từng bước bằng terminal và trình duyệt, tạo đơn bằng mode **cron-create**:

```powershell
& 'D:\\baitap\\php\\php.exe' scripts/test_existing_woocommerce.php 'D:\\baitap\\htdocs\\shopdongho' cron-create
```

Ghi ID mới được in ra, truy cập trang chủ bình thường và chờ Scheduled Action tự Complete. Sau khi Order CRM đã có, dùng ID đó với mode **cron-update**:

```powershell
& 'D:\\baitap\\php\\php.exe' scripts/test_existing_woocommerce.php 'D:\\baitap\\htdocs\\shopdongho' cron-update <TEST_ORDER_ID>
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
""")


def build_handover():
	write("HANDOVER.md", r"""
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
""".replace(r"D:\u005cbaitap\u005chtdocs\u005cshopdongho", "D:\\baitap\\htdocs\\shopdongho"))


def main():
	schemas = load("DATA_DICTIONARY.json")["doctypes"]
	actual = {row["name"]: row for row in load("documentation_audit.json")["hsk_doctypes"]}
	assert len(schemas) == 5 and sum(len(s["fields"]) for s in schemas) == 53
	for schema in schemas:
		fields = {f["fieldname"]: f for f in actual[schema["name"]]["fields"]}
		for field in schema["fields"]:
			assert field["fieldname"] in fields
			for key in ("fieldtype", "options", "reqd", "unique"):
				assert (field.get(key) or 0) == (fields[field["fieldname"]].get(key) or 0)
	build_dictionary(schemas)
	build_tests()
	build_implementation()
	build_api()
	build_demo()
	build_handover()
	print("Created 6 Vietnamese Markdown documents; checked 5 DocTypes, 53 fields and 37 test case records.")


if __name__ == "__main__":
	main()
