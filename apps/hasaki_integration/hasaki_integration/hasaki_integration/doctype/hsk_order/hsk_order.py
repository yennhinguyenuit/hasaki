import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from hasaki_integration.validation import nonnegative, validate_item


class HSKOrder(Document):
	def validate(self):
		previous = self.get_doc_before_save()
		if previous and previous.source_channel == "WooCommerce":
			for fieldname in ("source_channel", "source_store", "external_order_id", "integration_key"):
				if previous.get(fieldname) != self.get(fieldname):
					frappe.throw("The source identity of an existing WooCommerce order cannot change")
		if self.currency != "VND":
			frappe.throw("Only VND is supported by Technical Contract v1.1")
		self.integration_key = self.integration_key or None
		if self.source_channel == "WooCommerce":
			if not self.source_store or not self.external_order_id:
				frappe.throw("WooCommerce orders require source_store and external_order_id")
			expected = f"woo:{self.source_store}:{self.external_order_id}"
			if self.integration_key and self.integration_key != expected:
				frappe.throw("Invalid WooCommerce integration_key")
			self.integration_key = expected
		for fieldname in ("grand_total", "discount_total", "shipping_total"):
			nonnegative(self.get(fieldname), fieldname)
		for item in self.items:
			validate_item(item)
		# Rebuild from the persisted audit trail; read_only alone is only a UI
		# constraint and would still allow a REST caller to replace child rows.
		self.set("status_history", [row.as_dict() for row in previous.status_history] if previous else [])
		if self.is_new() or self.has_value_changed("status"):
			self.append("status_history", {
				"status": self.status,
				"changed_at": now_datetime(),
				"changed_by": frappe.session.user,
				"note": "Initial status" if self.is_new() else "Status changed",
			})
		if self.is_new():
			self.payment_status = "Pending"
		else:
			# Payments, rather than order status, determine whether an order is paid.
			from hasaki_integration.payments import get_payment_status

			self.payment_status = get_payment_status(self.name, self.grand_total)
