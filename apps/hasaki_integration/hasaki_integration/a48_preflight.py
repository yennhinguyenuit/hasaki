"""Read-only inspection before implementing the A4.8 technical contract.

Run from Bench with:
    bench --site crm.localhost execute hasaki_integration.a48_preflight.inspect_site

This module does not create documents, credentials, roles, or master data.
"""

import frappe


HSK_DOCTYPES = (
	"HSK Order",
	"HSK Order Item",
	"HSK Order Status History",
	"HSK Payment",
	"HSK Integration Event",
)


def _describe_doctype(name):
	if not frappe.db.exists("DocType", name):
		return {"name": name, "exists": False}

	meta = frappe.get_meta(name)
	return {
		"name": name,
		"exists": True,
		"module": meta.module,
		"custom": meta.custom,
		"istable": meta.istable,
		"autoname": meta.autoname,
		"fields": [
			{
				key: field.get(key)
				for key in ("fieldname", "fieldtype", "options", "reqd", "unique", "default")
			}
			for field in meta.fields
			if field.fieldtype not in ("Section Break", "Column Break", "Tab Break")
		],
		"permissions": [
			{key: permission.get(key) for key in ("role", "read", "write", "create", "delete")}
			for permission in meta.permissions
		],
	}


def inspect_site():
	"""Return metadata and existing prerequisites without exposing API credentials.

	Intended for local Bench execution by the site operator; not a whitelisted API.
	"""
	from frappe.utils import get_bench_path, getdate

	return {
		"site": frappe.local.site,
		"inspection_date": str(getdate()),
		"bench_path": get_bench_path(),
		"installed_apps": {
			app: getattr(frappe.get_module(app), "__version__", None)
			for app in frappe.get_installed_apps()
		},
		"hsk_doctypes": [_describe_doctype(name) for name in HSK_DOCTYPES],
		"related_doctypes": [
			_describe_doctype(name)
			for name in ("CRM Lead", "CRM Lead Source", "CRM Lead Status", "Comment")
		],
		"existing_lead_sources": frappe.get_all("CRM Lead Source", pluck="name", order_by="name"),
		"existing_lead_statuses": frappe.get_all("CRM Lead Status", pluck="name", order_by="name"),
		"existing_roles": frappe.get_all(
			"Role",
			filters={"name": ["in", ["System Manager", "Sales Manager", "Sales User", "CSKH Hasaki"]]},
			pluck="name",
			order_by="name",
		),
		"module": frappe.get_all(
			"Module Def",
			filters={"name": "Hasaki Integration"},
			fields=["name", "app_name", "custom"],
		),
		"enabled_users_with_api_key": frappe.db.count("User", {"enabled": 1, "api_key": ["is", "set"]}),
	}
