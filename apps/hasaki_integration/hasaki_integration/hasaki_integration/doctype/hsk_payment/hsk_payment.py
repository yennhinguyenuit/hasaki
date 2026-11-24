import frappe
from frappe.model.document import Document

from hasaki_integration.payments import update_payment_status
from hasaki_integration.validation import nonnegative


class HSKPayment(Document):
	def before_validate(self):
		# Serialize all payments for a parent before inserting/updating a child.
		if self.order:
			frappe.db.get_value("HSK Order", self.order, "name", for_update=True)

	def validate(self):
		nonnegative(self.amount, "amount")
		self.payment_integration_key = self.payment_integration_key or None
		if self.status == "Paid" and not self.paid_at:
			frappe.throw("A Paid payment requires paid_at")
		if not self.is_new():
			previous = self.get_doc_before_save()
			if previous and previous.order != self.order:
				frappe.throw("The order of an existing payment cannot be changed")
			if previous and previous.payment_integration_key != self.payment_integration_key:
				frappe.throw("The integration key of an existing payment cannot be changed")

	def on_update(self):
		update_payment_status(self.order)

	def on_trash(self):
		frappe.db.get_value("HSK Order", self.order, "name", for_update=True)

	def after_delete(self):
		if frappe.db.exists("HSK Order", self.order):
			update_payment_status(self.order)
