"""Real HTTP tests against the existing local site, without master-data fixtures.

Run with Bench execute, not the Frappe test runner (which may seed master data):
    bench --site crm.localhost execute hasaki_integration.tests.test_integration_http.run_lead

Reuse an existing Sales User's integration token when available; otherwise use
a temporary credential which is restored in finally. New transaction test
records are retained. No masters are created and no existing business records
are edited or deleted.
"""

import base64
import copy
import hashlib
import hmac
import io
import json
import secrets
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import frappe
import requests
from frappe.utils.password import get_decrypted_password, set_encrypted_password

LEAD_PATH = "/api/method/hasaki_integration.wordpress.receive_lead"
ORDER_PATH = "/api/method/hasaki_integration.woocommerce.receive_order"
MASTER_DOCTYPES = ("Contact", "CRM Product", "HSK Product Category", "CRM Lead Source", "Role", "User")


def snapshot():
	frappe.db.rollback()
	result = {}
	for dt in MASTER_DOCTYPES:
		rows = frappe.get_all(dt, fields=["*"], order_by="name")
		result[dt] = {
			"count": len(rows),
			"sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest(),
			"field_hashes": {
				key: hashlib.sha256(json.dumps([r[key] for r in rows], default=str).encode()).hexdigest()
				for key in (rows[0] if rows else {})
			},
		}
	return result


class LeadHTTPTests(unittest.TestCase):
	base = "http://127.0.0.1:8000"
	user = "tuvan@hasaki.example"
	headers = {}

	def setUp(self):
		self.payload = {
			"submission_id": "a48-test-" + uuid.uuid4().hex,
			"first_name": "A4.8 TEST", "last_name": "Lead",
			"phone": "0900000000", "email": "a48-test@example.invalid",
			"message": "Yeu cau tu van A4.8\nDong thu hai", "consent": True,
		}

	def post(self, payload=None, headers=None, **kwargs):
		response = requests.post(
			self.base + LEAD_PATH, json=self.payload if payload is None else payload,
			headers=self.headers if headers is None else headers, timeout=30, **kwargs,
		)
		return response, response.json().get("message", {})

	def event(self):
		frappe.db.rollback()
		return frappe.db.get_value("HSK Integration Event", {
			"source": "WordPress", "external_object_id": self.payload["submission_id"],
		}, ["name", "status", "reference_doctype", "reference_name", "error_summary"], as_dict=True)

	def test_valid_lead_mapping_and_comment(self):
		response, result = self.post()
		self.assertEqual(response.status_code, 200, response.text)
		self.assertTrue(result["ok"], result)
		frappe.db.rollback()
		lead = frappe.get_doc("CRM Lead", result["data"]["lead"])
		self.assertEqual(lead.first_name, self.payload["first_name"])
		self.assertEqual(lead.last_name, self.payload["last_name"])
		self.assertEqual(lead.mobile_no, self.payload["phone"])
		self.assertEqual(lead.email, self.payload["email"])
		self.assertEqual(lead.source, "Web Form")
		comments = frappe.get_all("Comment", filters={
			"reference_doctype": "CRM Lead", "reference_name": lead.name, "comment_type": "Comment",
		}, pluck="content")
		self.assertEqual(len(comments), 1)
		self.assertIn("Yeu cau tu van A4.8", comments[0])
		self.assertIn("Dong thu hai", comments[0])
		self.assertEqual(self.event().status, "Processed")
		self.assertEqual(self.event().reference_name, lead.name)

	def test_duplicate_submission_returns_original_lead(self):
		_, first = self.post()
		response, second = self.post()
		self.assertEqual(response.status_code, 200, response.text)
		self.assertTrue(second["idempotent"])
		self.assertEqual(first["data"], second["data"])

	def test_concurrent_duplicate_submission(self):
		with ThreadPoolExecutor(max_workers=4) as executor:
			results = list(executor.map(lambda _: self.post(), range(4)))
		for response, result in results:
			self.assertEqual(response.status_code, 200, response.text)
			self.assertTrue(result["ok"], result)
		self.assertEqual(len({result["data"]["lead"] for _, result in results}), 1)
		self.assertEqual(sum(not result["idempotent"] for _, result in results), 1)

	def test_reused_key_with_different_payload_conflicts(self):
		self.post()
		self.payload["message"] = "Changed request"
		response, result = self.post()
		self.assertEqual(response.status_code, 409)
		self.assertEqual(result["code"], "CONFLICT")

	def test_no_token_rejected_without_event(self):
		response, result = self.post(headers={"Host": "crm.localhost"})
		self.assertEqual(response.status_code, 401)
		self.assertEqual(result["code"], "UNAUTHORIZED")
		self.assertIsNone(self.event())

	def test_invalid_token_rejected_without_event(self):
		response, result = self.post(headers={"Host": "crm.localhost", "Authorization": "token invalid:invalid"})
		self.assertEqual(response.status_code, 401, response.text)
		self.assertEqual(result["code"], "UNAUTHORIZED")
		self.assertIsNone(self.event())

	def test_false_consent_rejected_and_logged(self):
		self.payload["consent"] = False
		response, result = self.post()
		self.assertEqual(response.status_code, 400, response.text)
		self.assertEqual(result["code"], "VALIDATION_ERROR")
		self.assertEqual(self.event().status, "Failed")
		self.assertIsNone(self.event().reference_name)

	def test_consent_requires_boolean(self):
		for consent in ("true", 1, "1", None):
			self.payload["submission_id"] = "a48-test-" + uuid.uuid4().hex
			self.payload["consent"] = consent
			response, result = self.post()
			self.assertEqual(response.status_code, 400, result)

	def test_missing_fields_do_not_create_lead(self):
		frappe.db.rollback()
		before = frappe.db.count("CRM Lead")
		for field in ("submission_id", "first_name", "phone", "message"):
			payload = dict(self.payload, submission_id="a48-test-" + uuid.uuid4().hex)
			payload.pop(field)
			response, result = self.post(payload)
			self.assertEqual(response.status_code, 400, result)
		frappe.db.rollback()
		self.assertEqual(frappe.db.count("CRM Lead"), before)

	def test_invalid_email_and_phone(self):
		for field, value in (("email", "not-an-email"), ("phone", "abc"), ("phone", "123")):
			payload = dict(self.payload, submission_id="a48-test-" + uuid.uuid4().hex)
			payload[field] = value
			response, result = self.post(payload)
			self.assertEqual(response.status_code, 400, result)

	def test_optional_fields_can_be_omitted(self):
		self.payload.pop("last_name")
		self.payload.pop("email")
		response, result = self.post()
		self.assertEqual(response.status_code, 200, response.text)
		self.assertTrue(result["ok"], result)

	def test_html_message_is_safe(self):
		self.payload["message"] = '<script>alert(1)</script>Tu van <b>san pham</b>'
		_, result = self.post()
		frappe.db.rollback()
		content = frappe.db.get_value("Comment", {
			"reference_doctype": "CRM Lead", "reference_name": result["data"]["lead"],
			"comment_type": "Comment",
		}, "content")
		self.assertNotIn("<script>", content)
		self.assertIn("Tu van", content)

	def test_get_is_not_allowed(self):
		response = requests.get(self.base + LEAD_PATH, headers=self.headers, timeout=30)
		self.assertIn(response.status_code, (403, 405))


class RecordingResult(unittest.TextTestResult):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.records = []

	def addSuccess(self, test):
		super().addSuccess(test)
		self.records.append({"test": test.id(), "status": "Passed"})

	def addFailure(self, test, err):
		super().addFailure(test, err)
		self.records.append({"test": test.id(), "status": "Failed", "detail": self._exc_info_to_string(err, test)})

	def addError(self, test, err):
		super().addError(test, err)
		self.records.append({"test": test.id(), "status": "Failed", "detail": self._exc_info_to_string(err, test)})


def run_lead():
	return _run(LeadHTTPTests, "test_results_lead.json")


class WooHTTPTests(unittest.TestCase):
	base = "http://127.0.0.1:8000"
	user = "tuvan@hasaki.example"
	headers = {}
	source_url = "http://a48-test.invalid"
	source_store = "a48-test"
	secret = ""

	def setUp(self):
		frappe.db.rollback()
		self.product = frappe.get_all("CRM Product", filters={"disabled": 0},
			fields=["name", "product_code", "custom_cost_price"], limit=1)[0]
		self.payload = {
			"id": int(uuid.uuid4().hex[:12], 16), "status": "pending", "currency": "VND",
			"date_created_gmt": "2026-11-23T03:00:00", "date_modified_gmt": "2026-11-23T03:00:00",
			"date_paid_gmt": None, "total": "100000.00", "discount_total": "10000.00",
			"shipping_total": "10000.00", "payment_method": "cod", "transaction_id": "",
			"billing": {"first_name": "A4.8 TEST", "last_name": "Guest",
				"phone": "0900000000", "email": "a48-test-guest@example.invalid"},
			"line_items": [{"id": 1, "sku": self.product.product_code, "quantity": 1,
				"subtotal": "100000.00", "total": "90000.00"}],
		}
		self.delivery = "a48-test-" + uuid.uuid4().hex

	def post(self, payload=None, topic="order.created", delivery=None, bad_signature=False, source=None):
		payload = self.payload if payload is None else payload
		raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
		signature = base64.b64encode(hmac.new(self.secret.encode(), raw, hashlib.sha256).digest()).decode()
		headers = {
			"Host": "crm.localhost", "Content-Type": "application/json",
			"X-WC-Webhook-Source": source or self.source_url,
			"X-WC-Webhook-Topic": topic,
			"X-WC-Webhook-Delivery-ID": delivery or self.delivery,
			"X-WC-Webhook-Signature": "invalid" if bad_signature else signature,
		}
		response = requests.post(self.base + ORDER_PATH, data=raw, headers=headers, timeout=30)
		return response, response.json().get("message", {})

	def order(self):
		frappe.db.rollback()
		name = frappe.db.get_value("HSK Order", {"integration_key": f"woo:{self.source_store}:{self.payload['id']}"}, "name")
		return frappe.get_doc("HSK Order", name) if name else None

	def test_create_order_items_cost_snapshot_and_guest(self):
		response, result = self.post()
		self.assertEqual(response.status_code, 200, response.text)
		self.assertTrue(result["ok"], result)
		order = self.order()
		self.assertEqual(order.name, result["data"]["order"])
		self.assertEqual(order.status, "Pending")
		self.assertEqual(order.payment_status, "Pending")
		self.assertEqual(str(order.order_date), "2026-11-23 10:00:00")
		self.assertFalse(order.customer)
		self.assertEqual(order.guest_full_name, "A4.8 TEST Guest")
		self.assertEqual(order.grand_total, 100000)
		self.assertEqual(order.discount_total, 10000)
		self.assertEqual(len(order.items), 1)
		self.assertEqual(order.items[0].product, self.product.name)
		self.assertEqual(order.items[0].line_total, 90000)
		self.assertEqual(order.items[0].discount_amount, 10000)
		self.assertEqual(order.items[0].cost_price, self.product.custom_cost_price)
		self.assertEqual(len(order.status_history), 1)
		self.assertEqual(frappe.db.count("HSK Payment", {"order": order.name}), 0)

	def test_update_existing_order_and_history_without_automatic_payment(self):
		_, first = self.post()
		self.payload.update(status="processing", date_modified_gmt="2026-11-23T04:00:00")
		response, result = self.post(topic="order.updated", delivery=self.delivery + "-2")
		self.assertEqual(response.status_code, 200, response.text)
		order = self.order()
		self.assertEqual(order.name, first["data"]["order"])
		self.assertEqual(order.status, "Processing")
		self.assertEqual(order.payment_status, "Pending")
		self.assertEqual([h.status for h in order.status_history], ["Pending", "Processing"])
		self.assertEqual(frappe.db.count("HSK Payment", {"order": order.name}), 0)

	def test_confirmed_payment_created_once(self):
		self.payload.update(status="processing", date_paid_gmt="2026-11-23T03:00:00", transaction_id="a48-test-txn")
		response, result = self.post()
		self.assertEqual(response.status_code, 200, response.text)
		self.post(delivery=self.delivery + "-same-payload")
		self.payload["date_modified_gmt"] = "2026-11-23T04:00:00"
		response, result = self.post(topic="order.updated", delivery=self.delivery + "-new-version")
		self.assertEqual(response.status_code, 200, response.text)
		order = self.order()
		self.assertEqual(order.payment_status, "Paid")
		payments = frappe.get_all("HSK Payment", filters={"order": order.name}, fields=["status", "amount", "paid_at"])
		self.assertEqual(len(payments), 1)
		self.assertEqual(payments[0].status, "Paid")
		self.assertEqual(payments[0].amount, 100000)
		self.assertEqual(str(payments[0].paid_at), "2026-11-23 10:00:00")

	def test_duplicate_delivery_returns_same_order(self):
		_, first = self.post()
		response, second = self.post()
		self.assertEqual(response.status_code, 200, response.text)
		self.assertTrue(second["idempotent"])
		self.assertEqual(first["data"]["order"], second["data"]["order"])
		self.assertEqual(len(self.order().status_history), 1)

	def test_concurrent_duplicate_delivery(self):
		with ThreadPoolExecutor(max_workers=4) as executor:
			results = list(executor.map(lambda _: self.post(), range(4)))
		for response, result in results:
			self.assertEqual(response.status_code, 200, response.text)
			self.assertTrue(result["ok"], result)
		self.assertEqual(len({result["data"]["order"] for _, result in results}), 1)
		self.assertEqual(sum(not result["idempotent"] for _, result in results), 1)

	def test_same_native_delivery_id_can_deliver_different_orders(self):
		_, first = self.post()
		self.payload["id"] += 1
		response, second = self.post()
		self.assertEqual(response.status_code, 200, response.text)
		self.assertNotEqual(first["data"]["order"], second["data"]["order"])

	def test_same_native_delivery_id_can_deliver_newer_order_version(self):
		_, first = self.post()
		self.payload.update(status="processing", date_modified_gmt="2026-11-23T06:00:00")
		response, result = self.post(topic="order.updated")
		self.assertEqual(response.status_code, 200, response.text)
		self.assertEqual(first["data"]["order"], result["data"]["order"])
		self.assertEqual(self.order().status, "Processing")

	def test_bad_signature_has_no_event_or_order(self):
		response, result = self.post(bad_signature=True)
		self.assertEqual(response.status_code, 401, response.text)
		self.assertEqual(result["code"], "INVALID_SIGNATURE")
		self.assertIsNone(self.order())
		self.assertFalse(frappe.db.exists("HSK Integration Event", {"event_id": self.delivery}))

	def test_unknown_source_rejected(self):
		response, result = self.post(source="http://untrusted.invalid")
		self.assertEqual(response.status_code, 401, response.text)
		self.assertEqual(result["code"], "INVALID_SIGNATURE")
		self.assertIsNone(self.order())

	def test_unknown_sku_fails_without_product_creation(self):
		self.payload["line_items"][0]["sku"] = "A48-DOES-NOT-EXIST-" + uuid.uuid4().hex
		response, result = self.post()
		self.assertEqual(response.status_code, 422, response.text)
		self.assertEqual(result["code"], "SKU_NOT_FOUND")
		self.assertIsNone(self.order())
		self.assertEqual(frappe.db.get_value("HSK Integration Event", {"event_id": self.delivery}, "status"), "Failed")

	def test_stale_event_cannot_overwrite_order(self):
		self.payload.update(status="processing", date_modified_gmt="2026-11-23T05:00:00")
		self.post()
		self.payload.update(status="pending", date_modified_gmt="2026-11-23T04:00:00")
		response, result = self.post(topic="order.updated", delivery=self.delivery + "-old")
		self.assertEqual(response.status_code, 200, response.text)
		self.assertTrue(result["data"]["ignored_stale"])
		self.assertEqual(self.order().status, "Processing")
		self.assertEqual(len(self.order().status_history), 1)

	def test_equal_timestamp_different_payload_conflicts(self):
		self.post()
		self.payload["status"] = "processing"
		response, result = self.post(topic="order.updated", delivery=self.delivery + "-conflict")
		self.assertEqual(response.status_code, 409, response.text)
		self.assertEqual(result["code"], "CONFLICT")
		self.assertEqual(self.order().status, "Pending")

	def test_missing_order_update_does_not_create_order(self):
		response, result = self.post(topic="order.updated")
		self.assertEqual(response.status_code, 409, response.text)
		self.assertIsNone(self.order())

	def test_payment_conflict_rolls_back_order_and_history(self):
		self.payload.update(status="processing", date_paid_gmt="2026-11-23T03:00:00")
		self.post()
		self.payload.update(status="completed", total="200000.00", date_modified_gmt="2026-11-23T06:00:00")
		response, result = self.post(topic="order.updated", delivery=self.delivery + "-conflict")
		self.assertEqual(response.status_code, 409, response.text)
		order = self.order()
		self.assertEqual(order.grand_total, 100000)
		self.assertEqual(order.status, "Processing")
		self.assertEqual(len(order.status_history), 1)
		self.assertEqual(frappe.db.count("HSK Payment", {"order": order.name}), 1)

	def test_invalid_second_line_rolls_back_entire_order(self):
		line = copy.deepcopy(self.payload["line_items"][0])
		line.update(id=2, sku="A48-MISSING-" + uuid.uuid4().hex)
		self.payload["line_items"].append(line)
		response, result = self.post()
		self.assertEqual(response.status_code, 422, response.text)
		self.assertIsNone(self.order())

	def test_duplicate_line_ids_rejected(self):
		self.payload["line_items"].append(copy.deepcopy(self.payload["line_items"][0]))
		response, result = self.post()
		self.assertEqual(response.status_code, 400, response.text)
		self.assertIsNone(self.order())

	def test_invalid_money_and_currency_rejected(self):
		for value in ("NaN", "Infinity", "-1"):
			self.payload["id"] += 1
			self.payload["total"] = value
			response, result = self.post(delivery=self.delivery + value)
			self.assertEqual(response.status_code, 400, response.text)
		self.payload.update(id=self.payload["id"] + 1, total="100000", currency="USD")
		response, result = self.post(delivery=self.delivery + "-currency")
		self.assertEqual(response.status_code, 400, response.text)

	def test_activation_probe_writes_no_business_data(self):
		response = requests.post(self.base + ORDER_PATH, data={"webhook_id": "123"},
			headers={"Host": "crm.localhost"}, timeout=30)
		self.assertEqual(response.status_code, 200, response.text)
		self.assertEqual(response.json()["message"]["code"], "WEBHOOK_PROBE")
		self.assertIsNone(self.order())


def run_woocommerce():
	config_path = Path(frappe.get_site_path("site_config.json"))
	original = config_path.read_bytes()
	config = json.loads(original)
	WooHTTPTests.secret = secrets.token_hex(32)
	stores = config.setdefault("hasaki_woocommerce_stores", {})
	if WooHTTPTests.source_url in stores:
		raise RuntimeError("The temporary test source URL is already configured")
	stores[WooHTTPTests.source_url] = {
		"source_store": WooHTTPTests.source_store, "secret": WooHTTPTests.secret, "user": WooHTTPTests.user,
	}
	try:
		config_path.write_text(json.dumps(config, indent=2) + "\n")
		return _run(WooHTTPTests, "test_results_woocommerce.json")
	finally:
		config_path.write_bytes(original)
		WooHTTPTests.secret = ""


def _run(test_class, report_name):
	baseline = snapshot()
	user = test_class.user
	if not frappe.db.exists("User", {"name": user, "enabled": 1}):
		raise RuntimeError("The existing test Sales User is required; no new user will be created")
	old_key = frappe.db.get_value("User", user, "api_key")
	old_secret = frappe.db.sql(
		"SELECT * FROM `__Auth` WHERE doctype=%s AND name=%s AND fieldname=%s",
		("User", user, "api_secret"), as_dict=True,
	)
	current_secret = get_decrypted_password("User", user, "api_secret", raise_exception=False)
	reuse_existing = bool(old_key and current_secret)
	key = old_key if reuse_existing else secrets.token_hex(16)
	secret = current_secret if reuse_existing else secrets.token_hex(24)
	test_class.headers = {"Host": "crm.localhost", "Authorization": f"token {key}:{secret}"}
	try:
		if not reuse_existing:
			frappe.db.set_value("User", user, "api_key", key, update_modified=False)
			set_encrypted_password("User", user, secret, fieldname="api_secret")
		frappe.db.commit()
		suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
		stream = io.StringIO()
		result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordingResult).run(suite)
	finally:
		frappe.db.rollback()
		if not reuse_existing:
			frappe.db.set_value("User", user, "api_key", old_key, update_modified=False)
			frappe.db.sql("DELETE FROM `__Auth` WHERE doctype=%s AND name=%s AND fieldname=%s", ("User", user, "api_secret"))
			if old_secret:
				row = old_secret[0]
				frappe.db.sql(
					"INSERT INTO `__Auth` (doctype,name,fieldname,password,encrypted) VALUES (%s,%s,%s,%s,%s)",
					(row.doctype, row.name, row.fieldname, row.password, row.encrypted),
				)
		frappe.db.commit()
		test_class.headers = {}
	after = snapshot()
	changed_fields = {
		dt: [key for key, value in baseline[dt]["field_hashes"].items()
			if value != after[dt]["field_hashes"].get(key)]
		for dt in MASTER_DOCTYPES if baseline[dt] != after[dt]
	}
	# Session.update() in the unmodified framework periodically updates User
	# last_active during real HTTP traffic. Record it without treating session
	# telemetry as a business/master-data modification.
	business_unchanged = (
		all(baseline[dt]["count"] == after[dt]["count"] for dt in MASTER_DOCTYPES)
		and all(dt == "User" and set(fields) <= {"last_active"} for dt, fields in changed_fields.items())
	)
	report = {
		"site": frappe.local.site, "checked_at": str(frappe.utils.now_datetime()),
		"transport": getattr(test_class, "transport", "real HTTP on port 8000"),
		"tests_run": result.testsRun,
		"passed": result.wasSuccessful() and business_unchanged, "results": result.records,
		"masters_before": baseline, "masters_after": after,
		"master_business_data_unchanged": business_unchanged,
		"master_data_exactly_unchanged": baseline == after,
		"allowed_runtime_change": "User.last_active only; automatically updated by the core Frappe HTTP session",
		"changed_master_fields": changed_fields,
		"credentials": "Reused the existing integration token without rotating it" if reuse_existing else "Temporary token on an existing user; original credentials restored",
		"transaction_test_records": "Retained with a48-test- external identifiers and A4.8 TEST names",
	}
	path = Path(frappe.get_app_path("hasaki_integration")).parent / "docs" / report_name
	path.write_text(json.dumps(report, indent=2, default=str) + "\n")
	print(stream.getvalue())
	print("Master business data unchanged:", business_unchanged)
	print("Recorded master field changes:", changed_fields)
	if not report["passed"]:
		raise AssertionError(f"Tests or master data integrity check failed; inspect {path}")
	return {"passed": report["passed"], "tests_run": result.testsRun, "report": str(path)}
