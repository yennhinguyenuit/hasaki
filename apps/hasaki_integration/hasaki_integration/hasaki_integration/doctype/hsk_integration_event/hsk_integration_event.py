import re

import frappe
from frappe.model.document import Document


class HSKIntegrationEvent(Document):
	def validate(self):
		if not re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256 or ""):
			frappe.throw("payload_sha256 must be a SHA256 digest")
		if self.reference_name and not self.reference_doctype:
			frappe.throw("reference_name requires reference_doctype")
		if self.status == "Processed" and not (
			self.reference_doctype and self.reference_name and self.processed_at
		):
			frappe.throw("Processed events require a reference and processed_at")
