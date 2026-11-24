"""Read-only diagnostics for Desk assets and query validation. Not whitelisted."""

import hashlib
import json
import re
import traceback
from pathlib import Path

import frappe
import requests

DOCTYPES = ("DocType", "HSK Order", "HSK Payment", "HSK Integration Event", "CRM Lead", "CRM Deal", "Contact")
ROOT = Path("/workspace/hasaki_integration")
SITES = Path("/home/frappe/frappe-bench/sites")


def run_after():
	return run("after")


def run(phase="after"):
	from frappe.desk import reportview
	from frappe.model import optional_fields

	frappe.set_user("Administrator")
	assets = json.loads((SITES / "assets/assets.json").read_text())
	missing = [v for v in assets.values() if v.startswith("/assets/frappe/") and not (SITES / v.lstrip("/")).is_file()]
	assert not missing, missing
	asset = assets["desk.bundle.js"]
	content = (SITES / asset.lstrip("/")).read_bytes()
	served = requests.get("http://127.0.0.1:8000" + asset, headers={"Host": "crm.localhost"}, timeout=30)
	served.raise_for_status()
	assert hashlib.sha256(served.content).digest() == hashlib.sha256(content).digest()
	match = re.search(rb'std_fields_list:\s*\[([^]]+)\]', content)
	std_fields = json.loads(b"[" + match[1] + b"]")
	result = {"checked_at": str(frappe.utils.now()), "phase": phase, "frappe_version": frappe.__version__,
		"optional_fields": list(optional_fields), "desk_asset": asset,
		"desk_asset_sha256": hashlib.sha256(content).hexdigest(), "served_asset_matches_disk": True,
		"bundle_std_fields": std_fields, "missing_frappe_manifest_files": missing,
		"cached_manifest_matches_disk": frappe.utils.get_assets_json()["desk.bundle.js"] == asset,
		"doctypes": [], "http": []}
	for dt in DOCTYPES:
		meta = frappe.get_meta(dt)
		params = {"doctype": dt, "fields": [f"`tab{dt}`.`{f}`" for f in std_fields],
			"filters": [], "group_by": f"`tab{dt}`.`name`", "order_by": f"`tab{dt}`.`modified` desc",
			"start": 0, "page_length": 20, "with_comment_count": 1, "view": "List", "save_user_settings": "false"}
		entry = {"doctype": dt, "request": params, "has_comments_column": frappe.db.has_column(dt, "_comments"),
			"has_comments_docfield": bool(meta.get_field("_comments")),
			"custom_comments_fields": frappe.get_all("Custom Field", filters={"dt": dt, "fieldname": "_comments"}, pluck="name"),
			"list_view_settings": frappe.db.get_value("List View Settings", dt, "*")}
		settings = frappe.db.sql("select user, data from `__UserSettings` where doctype=%s", dt, as_dict=True)
		entry["user_settings"] = [{"user": r.user, "contains_comments": "_comments" in (r.data or ""), "data": r.data} for r in settings]
		frappe.local.form_dict = frappe._dict(params)
		try:
			data = reportview.get()
			entry.update(status="Passed", row_count=len(data.get("values", [])))
		except Exception:
			entry.update(status="Failed", traceback=traceback.format_exc())
		result["doctypes"].append(entry)
	# Use the existing integration API token through standard Frappe authentication.
	from frappe.utils.password import get_decrypted_password
	user = "tuvan@hasaki.example"
	key = frappe.db.get_value("User", user, "api_key")
	secret = get_decrypted_password("User", user, "api_secret", raise_exception=False)
	assert key and secret, "Existing integration credential required"
	session = requests.Session()
	session.headers.update({"Authorization": f"token {key}:{secret}"})
	result["http_user"] = user
	for dt in DOCTYPES:
		params = next(e["request"] for e in result["doctypes"] if e["doctype"] == dt)
		serialized = {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in params.items()}
		response = session.get("http://127.0.0.1:8000/api/method/frappe.desk.reportview.get",
			params=serialized, headers={"Host": "crm.localhost"}, timeout=30)
		body = response.json()
		result["http"].append({"doctype": dt, "status_code": response.status_code,
			"exc_type": body.get("exc_type"), "exception": body.get("exception"),
			"traceback": body.get("exc"), "row_count": len((body.get("message") or {}).get("values", []))})
		if response.status_code == 200:
			assert "_comments" not in (body.get("message") or {}).get("keys", [])
	if phase == "after":
		assert "_comments" not in std_fields
		assert all(e["status"] == "Passed" for e in result["doctypes"])
		for entry in result["http"]:
			expected = 403 if entry["doctype"] in ("DocType", "HSK Integration Event") else 200
			assert entry["status_code"] == expected, entry
		result["security_checks"] = []
		base = {"doctype": "HSK Order", "fields": '["name"]', "filters": "[]", "page_length": 1,
			"with_comment_count": 1, "save_user_settings": "false"}
		checks = {
			"comments_field": {"fields": '["name", "_comments"]'},
			"comments_filter": {"filters": '[["_comments", "like", "%test%"]]'},
			"comments_or_filter": {"or_filters": '[["_comments", "like", "%test%"]]'},
			"comments_group_by": {"group_by": "`tabHSK Order`.`_comments`"},
			"comments_order_by": {"order_by": "`tabHSK Order`.`_comments` desc"},
			"comments_expression": {"fields": '["name", "coalesce(_comments, name) as leak"]'},
			"unknown_field": {"fields": '["name", "a48_nonexistent_field"]'},
		}
		for name, override in checks.items():
			response = session.get("http://127.0.0.1:8000/api/method/frappe.desk.reportview.get",
				params={**base, **override}, headers={"Host": "crm.localhost"}, timeout=30)
			body = response.json()
			observational = name in ("comments_group_by", "comments_order_by")
			if not observational:
				assert response.status_code in (403, 417), (name, response.status_code)
			else:
				assert "_comments" not in (body.get("message") or {}).get("keys", [])
			result["security_checks"].append({"case": name, "status": "Observed" if observational else "Passed", "http_status": response.status_code,
				"exc_type": body.get("exc_type"), "exception": body.get("exception")})
		response = session.get("http://127.0.0.1:8000/api/method/frappe.desk.reportview.get",
			params=base, headers={"Host": "crm.localhost"}, timeout=30)
		assert response.status_code == 200
		keys = response.json()["message"]["keys"]
		assert "_comments" not in keys and "_comment_count" in keys
		result["security_checks"].append({"case": "comment_count_without_raw_comments", "status": "Passed", "http_status": 200})
	frappe.db.rollback()
	path = ROOT / "docs" / f"test_results_list_view_{phase}.json"
	path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
	return {"report": str(path), "asset": asset, "bundle_has_comments": "_comments" in std_fields,
		"backend": [e["status"] for e in result["doctypes"]], "http": [e["status_code"] for e in result["http"]]}
