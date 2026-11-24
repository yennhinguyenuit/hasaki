"""Validation shared by transaction controllers and integration endpoints."""

from decimal import Decimal, InvalidOperation

import frappe


def nonnegative(value, fieldname):
	try:
		number = Decimal(str(value if value is not None else 0))
		if not number.is_finite() or number < 0:
			raise InvalidOperation
	except (InvalidOperation, ValueError, TypeError):
		frappe.throw(f"{fieldname} must be a finite nonnegative number", frappe.ValidationError)
	return number


def validate_item(item):
	if nonnegative(item.qty, "qty") <= 0:
		frappe.throw("qty must be greater than zero")
	for fieldname in ("unit_price", "discount_amount", "line_total", "cost_price"):
		nonnegative(item.get(fieldname), fieldname)
	code = frappe.db.get_value("CRM Product", item.product, "product_code")
	if not code or code != item.sku:
		frappe.throw("product and sku must reference the same existing CRM Product")
