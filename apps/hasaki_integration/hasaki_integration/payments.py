from decimal import Decimal

import frappe


def get_payment_status(order, grand_total):
	# A current locking read avoids a stale REPEATABLE READ snapshot when two
	# distinct partial payments arrive concurrently for the same order.
	payments = frappe.db.sql(
		"SELECT status, amount FROM `tabHSK Payment` WHERE `order`=%s FOR UPDATE", (order,), as_dict=True
	)
	paid = sum((Decimal(str(p.amount)) for p in payments if p.status == "Paid"), Decimal(0))
	if any(p.status == "PartiallyRefunded" for p in payments):
		return "PartiallyRefunded"
	if any(p.status == "Refunded" for p in payments):
		return "PartiallyRefunded" if paid else "Refunded"
	if payments and any(p.status == "Paid" for p in payments) and paid >= Decimal(str(grand_total)):
		return "Paid"
	if payments and all(p.status == "Failed" for p in payments):
		return "Failed"
	return "Pending"


def update_payment_status(order):
	total = frappe.db.get_value("HSK Order", order, "grand_total", for_update=True)
	frappe.db.set_value("HSK Order", order, "payment_status", get_payment_status(order, total))
