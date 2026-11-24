"""Materialize the five v1.1 DocType schemas and their data dictionary.

Only writes source files. Never connects to a Frappe site.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "hasaki_integration" / "hasaki_integration" / "doctype"
ORDER_STATES = "Pending\nProcessing\nShipping\nCompleted\nCancelled"
PAYMENT_STATES = "Pending\nPaid\nFailed\nPartiallyRefunded\nRefunded"


def field(name, kind="Data", **kwargs):
	return {"fieldname": name, "label": name.replace("_", " ").title(), "fieldtype": kind, **kwargs}


def money(name, **kwargs):
	return field(name, "Currency", precision="2", **kwargs)


def permissions(event=False):
	result = []
	for role in ("System Manager", "Sales Manager", "Sales User", "CSKH Hasaki"):
		row = {"role": role, "read": 1, "select": 1}
		if not event:
			row.update(create=1, write=1, report=1, print=1)
			if role == "System Manager":
				row["delete"] = 1
		elif role not in ("System Manager", "Sales Manager"):
			continue
		result.append(row)
	return result


SCHEMAS = {
	"HSK Order": [
		field("customer", "Link", options="Contact"),
		field("lead", "Link", options="CRM Lead"),
		field("deal", "Link", options="CRM Deal"),
		field("source_channel", "Select", options="WooCommerce\nPOS\nManual", default="Manual", reqd=1, in_list_view=1),
		field("source_store"),
		field("external_order_id"),
		field("integration_key", unique=1, read_only=1),
		field("order_date", "Datetime", reqd=1),
		field("status", "Select", options=ORDER_STATES, default="Pending", reqd=1, in_list_view=1),
		field("payment_status", "Select", options=PAYMENT_STATES, default="Pending", reqd=1, read_only=1),
		field("currency", default="VND", reqd=1),
		money("grand_total", reqd=1, in_list_view=1),
		money("discount_total", default="0"),
		money("shipping_total", default="0"),
		field("guest_full_name"),
		field("guest_phone"),
		field("guest_email", options="Email"),
		field("items", "Table", options="HSK Order Item", reqd=1),
		field("status_history", "Table", options="HSK Order Status History", read_only=1),
		field("last_source_modified_at", "Datetime", read_only=1),
		field("last_source_payload_sha256", read_only=1, length=64),
	],
	"HSK Order Item": [
		field("product", "Link", options="CRM Product", reqd=1, in_list_view=1),
		field("external_line_id"),
		field("sku", reqd=1, in_list_view=1),
		field("qty", "Float", precision="6", reqd=1, in_list_view=1),
		money("unit_price", reqd=1, in_list_view=1),
		money("discount_amount", default="0"),
		money("line_total", reqd=1, in_list_view=1),
		money("cost_price", default="0"),
		field("loyalty_eligible", "Check", default="0"),
	],
	"HSK Order Status History": [
		field("status", "Select", options=ORDER_STATES, reqd=1, in_list_view=1),
		field("changed_at", "Datetime", reqd=1, in_list_view=1),
		field("changed_by", "Link", options="User", reqd=1, in_list_view=1),
		field("note", "Small Text"),
	],
	"HSK Payment": [
		field("order", "Link", options="HSK Order", reqd=1, in_list_view=1),
		money("amount", reqd=1, in_list_view=1),
		field("payment_method", reqd=1),
		field("status", "Select", options=PAYMENT_STATES, default="Pending", reqd=1, in_list_view=1),
		field("transaction_id"),
		field("paid_at", "Datetime"),
		field("payment_proof", "Attach"),
		field("payment_integration_key", unique=1, read_only=1),
	],
	"HSK Integration Event": [
		field("source", "Select", options="WordPress\nWooCommerce", reqd=1, in_list_view=1),
		field("event_id", reqd=1),
		field("idempotency_key", unique=1, reqd=1),
		field("external_object_id", reqd=1),
		field("event_type", reqd=1, in_list_view=1),
		field("payload_sha256", reqd=1, length=64),
		field("status", "Select", options="Received\nProcessed\nFailed", reqd=1, default="Received", in_list_view=1),
		field("reference_doctype", "Link", options="DocType"),
		field("reference_name", "Dynamic Link", options="reference_doctype"),
		field("processed_at", "Datetime"),
		field("error_summary", "Small Text"),
	],
}


def build():
	TARGET.mkdir(parents=True, exist_ok=True)
	(TARGET / "__init__.py").touch()
	dictionary = {
		"technical_contract_version": "1.1", "app": "hasaki_integration", "doctypes": [],
		"relationships": [
			"HSK Order.customer -> Contact.name (optional; never creates Contact)",
			"HSK Order.lead -> CRM Lead.name (optional)",
			"HSK Order.deal -> CRM Deal.name (optional)",
			"HSK Order.items -> HSK Order Item (child table, at least one row)",
			"HSK Order.status_history -> HSK Order Status History (child table, controller-managed)",
			"HSK Order Item.product -> CRM Product.name; sku must equal product_code",
			"HSK Payment.order -> HSK Order.name (many payments per order)",
			"HSK Integration Event.reference_name -> reference_doctype (Dynamic Link)",
		],
		"lead_mapping": {
			"phone": "CRM Lead.mobile_no", "first_name": "CRM Lead.first_name",
			"last_name": "CRM Lead.last_name", "email": "CRM Lead.email",
			"message": "Comment.content (escaped text), reference_doctype=CRM Lead, reference_name=Lead.name",
			"source": "Existing CRM Lead Source: Web Form",
			"submission_id": "HSK Integration Event.event_id and external_object_id",
			"consent": "Must be JSON true; not stored in a new CRM/Contact field",
		},
		"controller_rules": [
			"Currency is VND; numeric money fields must be finite and nonnegative; qty > 0.",
			"WooCommerce order identity is immutable and integration_key=woo:{source_store}:{external_order_id}.",
			"Manual/POS integration_key can be null; multiple null keys are permitted.",
			"Persisted status history cannot be overwritten by incoming REST child rows.",
			"Order starts with Pending payment_status; Processing alone never creates a payment.",
			"Paid payments require paid_at; payment order and payment_integration_key are immutable.",
			"Payment status is aggregated from recorded payments; this app does not execute refunds.",
			"WooCommerce item cost_price is snapshotted on first import and preserved on updates.",
			"line_total is after line discounts; discount_total is not subtracted again.",
			"Event stores IDs, hash, result reference and a bounded error summary, never full customer payloads.",
		],
		"permission_notes": [
			"Child DocTypes inherit permissions from HSK Order.",
			"Order and Payment CRUD uses existing System Manager/Sales Manager/Sales User/CSKH Hasaki roles.",
			"Only System Manager can delete Order/Payment; Event is read-only for System Manager/Sales Manager.",
			"Internal endpoint code writes Event with ignore_permissions after authentication/authorization.",
			"No Role, User, Contact, Product, category, lead source or Contact custom fields are created.",
		],
	}
	for name, fields in SCHEMAS.items():
		child = name in ("HSK Order Item", "HSK Order Status History")
		slug = name.lower().replace(" ", "_")
		folder = TARGET / slug
		folder.mkdir(exist_ok=True)
		(folder / "__init__.py").touch()
		schema = {
			"doctype": "DocType", "name": name, "module": "Hasaki Integration",
			"engine": "InnoDB", "istable": int(child), "custom": 0,
			"field_order": [f["fieldname"] for f in fields], "fields": fields,
			"permissions": [] if child else permissions(event=name == "HSK Integration Event"),
			"sort_field": "modified", "sort_order": "DESC", "actions": [], "links": [], "states": [],
		}
		if not child:
			schema["autoname"] = {
				"HSK Order": "format:HSK-ORD-{YYYY}-{#####}",
				"HSK Payment": "format:HSK-PAY-{YYYY}-{#####}",
				"HSK Integration Event": "hash",
			}[name]
			schema["track_changes"] = int(name != "HSK Integration Event")
		(folder / (slug + ".json")).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
		dictionary["doctypes"].append(schema)
	(ROOT / "docs").mkdir(exist_ok=True)
	(ROOT / "docs" / "DATA_DICTIONARY.json").write_text(
		json.dumps(dictionary, indent=2) + "\n", encoding="utf-8"
	)


if __name__ == "__main__":
	build()
