from frappe.model.document import Document

from hasaki_integration.validation import validate_item


class HSKOrderItem(Document):
	def validate(self):
		validate_item(self)
