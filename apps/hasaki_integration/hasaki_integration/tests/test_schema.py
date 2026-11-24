import json
import unittest
from pathlib import Path

import frappe
from frappe.utils import now_datetime

from hasaki_integration.tests.test_integration_http import _run


class SchemaTests(unittest.TestCase):
	user = "tuvan@hasaki.example"
	transport = "Frappe controllers and live MariaDB metadata"

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("schema_test")

	def tearDown(self):
		frappe.db.rollback(save_point="schema_test")

	def manual_order(self):
		product = frappe.get_all("CRM Product", filters={"disabled": 0}, fields=["name", "product_code"], limit=1)[0]
		return frappe.get_doc({
			"doctype": "HSK Order", "source_channel": "Manual", "order_date": now_datetime(),
			"status": "Pending", "currency": "VND", "grand_total": 100000,
			"items": [{"product": product.name, "sku": product.product_code, "qty": 1,
				"unit_price": 100000, "line_total": 100000, "cost_price": 50000}],
		}).insert()

	def test_five_doctypes_match_source(self):
		root = Path(frappe.get_app_path("hasaki_integration")) / "hasaki_integration" / "doctype"
		files = sorted(root.glob("*/*.json"))
		self.assertEqual(len(files), 5)
		for path in files:
			source = json.loads(path.read_text())
			meta = frappe.get_meta(source["name"])
			self.assertEqual(meta.module, "Hasaki Integration")
			self.assertEqual(meta.custom, 0)
			self.assertEqual(meta.istable, source["istable"])
			for field in source["fields"]:
				actual = meta.get_field(field["fieldname"])
				self.assertIsNotNone(actual)
				for key in ("fieldtype", "options", "unique", "reqd"):
					self.assertEqual(actual.get(key) or 0, field.get(key) or 0, (source["name"], field["fieldname"], key))

	def test_unique_indexes_exist_in_database(self):
		for doctype, fieldname in (
			("HSK Order", "integration_key"), ("HSK Payment", "payment_integration_key"),
			("HSK Integration Event", "idempotency_key"),
		):
			indexes = frappe.db.sql(f"SHOW INDEX FROM `tab{doctype}`", as_dict=True)
			self.assertTrue(any(row.Column_name == fieldname and not row.Non_unique for row in indexes))

	def test_manual_orders_allow_multiple_empty_integration_keys(self):
		one, two = self.manual_order(), self.manual_order()
		self.assertNotEqual(one.name, two.name)
		self.assertFalse(one.integration_key)
		self.assertFalse(two.integration_key)

	def test_multiple_payments_aggregate_and_paid_at_required(self):
		order = self.manual_order()
		for amount in (40000, 60000):
			frappe.get_doc({"doctype": "HSK Payment", "order": order.name, "amount": amount,
				"payment_method": "cash", "status": "Paid", "paid_at": now_datetime()}).insert()
			order.reload()
			self.assertEqual(order.payment_status, "Pending" if amount == 40000 else "Paid")
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "HSK Payment", "order": order.name, "amount": 1,
				"payment_method": "cash", "status": "Paid"}).insert()

	def test_history_cannot_be_overwritten_from_resource_api_data(self):
		order = self.manual_order()
		original = order.status_history[0].name
		order.set("status_history", [])
		order.status = "Processing"
		order.save()
		order.reload()
		self.assertEqual(len(order.status_history), 2)
		self.assertEqual(order.status_history[0].name, original)
		self.assertEqual([row.status for row in order.status_history], ["Pending", "Processing"])

	def test_guest_permissions_and_event_read_only(self):
		for doctype in ("HSK Order", "HSK Payment", "HSK Integration Event"):
			for permission in ("read", "create", "write", "delete"):
				self.assertFalse(frappe.has_permission(doctype, permission, user="Guest"))
		self.assertTrue(frappe.has_permission("HSK Integration Event", "read", user="manager@hasaki.example"))
		self.assertFalse(frappe.has_permission("HSK Integration Event", "create", user="manager@hasaki.example"))


def run():
	return _run(SchemaTests, "test_results_schema.json")
